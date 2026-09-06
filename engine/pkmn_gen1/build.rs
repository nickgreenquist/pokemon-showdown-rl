// Builds the vendored pkmn/engine (MIT, (c) 2021-2024 pkmn contributors) with Zig
// and links the resulting static library into this crate. See
// docs/PKMN_ENGINE_RUST_PLAN.md §4.4.
use std::{env, path::PathBuf, process::Command};

/// How to invoke Zig: `PKMN_ZIG` override, else the pinned `ziglang` pip wheel
/// (`python -m ziglang`), else `zig` on PATH.
fn zig_cmd() -> Vec<String> {
    if let Ok(z) = env::var("PKMN_ZIG") {
        return vec![z];
    }
    for py in [
        env::var("PKMN_PYTHON").unwrap_or_default(),
        env::var("PYTHON").unwrap_or_default(),
        "python3".to_string(),
        "python".to_string(),
    ] {
        if py.is_empty() {
            continue;
        }
        let ok = Command::new(&py)
            .args(["-m", "ziglang", "version"])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false);
        if ok {
            return vec![py, "-m".into(), "ziglang".into()];
        }
    }
    vec!["zig".into()]
}

fn run(cmd: &[String], args: &[&str], cwd: &PathBuf) -> std::process::Output {
    Command::new(&cmd[0])
        .args(&cmd[1..])
        .args(args)
        .current_dir(cwd)
        .output()
        .unwrap_or_else(|e| panic!("failed to run {cmd:?}: {e}"))
}

/// The interpreter's shared-library directory, if one can be found.
fn python_libdir() -> Option<String> {
    for py in [
        env::var("PKMN_PYTHON").unwrap_or_default(),
        env::var("PYO3_PYTHON").unwrap_or_default(),
        env::var("PYTHON").unwrap_or_default(),
        "python3".to_string(),
    ] {
        if py.is_empty() {
            continue;
        }
        let out = Command::new(&py)
            .args([
                "-c",
                "import sysconfig;print(sysconfig.get_config_var('LIBDIR') or '')",
            ])
            .output()
            .ok()?;
        if out.status.success() {
            let d = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if !d.is_empty() && PathBuf::from(&d).is_dir() {
                return Some(d);
            }
        }
    }
    None
}

fn main() {
    let manifest = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let out = PathBuf::from(env::var("OUT_DIR").unwrap());
    let vendor = manifest.join("vendor/pkmn-engine");
    assert!(
        vendor.join("build.zig").exists(),
        "vendor/pkmn-engine is empty -- run: git submodule update --init \
         engine/pkmn_gen1/vendor/pkmn-engine"
    );
    let prefix = out.join("pkmn");
    let log = if cfg!(feature = "debug-log") { "true" } else { "false" };

    let zig = zig_cmd();
    let ver = run(&zig, &["version"], &vendor);
    let zig_version = String::from_utf8_lossy(&ver.stdout).trim().to_string();
    assert!(
        ver.status.success() && !zig_version.is_empty(),
        "zig not runnable -- see docs/PKMN_ENGINE_RUST_PLAN.md §4.1 \
         (pip install ziglang==0.16.0, or set PKMN_ZIG)"
    );

    // The vendored tree stays pristine: caches live under OUT_DIR.
    let cache = out.join("zig-cache");
    let gcache = out.join("zig-global-cache");
    let build = run(
        &zig,
        &[
            "build",
            "-j2", // resource discipline: never wider (session brief §2)
            &format!("-Dlog={log}"),
            "-Dshowdown=true",
            "-Dchance=false",
            "-Dcalc=false",
            "-Doptimize=ReleaseFast",
            "-Dpic=true",
            "-Dstrip=true",
            "--prefix",
            prefix.to_str().unwrap(),
            "--cache-dir",
            cache.to_str().unwrap(),
            "--global-cache-dir",
            gcache.to_str().unwrap(),
        ],
        &vendor,
    );
    assert!(
        build.status.success(),
        "zig build of pkmn/engine failed:\n{}",
        String::from_utf8_lossy(&build.stderr)
    );

    // The engine commit this artifact was built from, baked in for verify().
    let sha = Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(&vendor)
        .output()
        .ok()
        .filter(|o| o.status.success())
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
        .unwrap_or_else(|| "unknown".into());

    println!("cargo:rustc-env=PKMN_ENGINE_SHA={sha}");
    println!("cargo:rustc-env=PKMN_ZIG_VERSION={zig_version}");
    // `cargo test` links libpython (maturin's extension-module build does not),
    // and a conda libpython is not on the default dyld search path. Emit an rpath
    // to the interpreter's LIBDIR so the test binaries load. Harmless for the
    // extension build, which never resolves it.
    if let Some(libdir) = python_libdir() {
        println!("cargo:rustc-link-arg=-Wl,-rpath,{libdir}");
    }

    println!("cargo:rustc-link-search=native={}", prefix.join("lib").display());
    println!("cargo:rustc-link-lib=static=pkmn-showdown");
    #[cfg(target_os = "linux")]
    println!("cargo:rustc-link-lib=c");
    println!("cargo:rerun-if-changed=vendor/pkmn-engine/src");
    println!("cargo:rerun-if-changed=vendor/pkmn-engine/build.zig");
    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-env-changed=PKMN_ZIG");
    println!("cargo:rerun-if-env-changed=PKMN_PYTHON");

    // The generated header is what the committed bindings must match; expose its
    // path so a test can diff it if the pin ever moves.
    println!(
        "cargo:rustc-env=PKMN_HEADER={}",
        prefix.join("include/pkmn.h").display()
    );

    #[cfg(feature = "regen-bindings")]
    {
        bindgen::Builder::default()
            .header(prefix.join("include/pkmn.h").to_string_lossy().into_owned())
            .allowlist_function("pkmn_.*")
            .allowlist_type("pkmn_.*")
            .allowlist_var("PKMN_.*")
            .prepend_enum_name(false)
            .default_enum_style(bindgen::EnumVariation::Consts)
            .layout_tests(true)
            .generate()
            .expect("bindgen")
            .write_to_file(manifest.join("src/ffi_generated.rs"))
            .expect("write bindings");
    }
}
