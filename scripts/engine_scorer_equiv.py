"""Verify the scorer factorization is the SAME FUNCTION before touching prod.

The claim: scorer[0] is Linear(ctx_in + entity_dim -> width) applied to
[ctx ; e_i] for i in 0..9, where ctx is IDENTICAL in all ten slots. A linear
map over a concatenation splits exactly:

    W @ [ctx ; e_i] + b  ==  (W[:, :ctx_in] @ ctx + b)  +  W[:, ctx_in:] @ e_i

so the ctx half is one GEMM per ROW instead of ten. Everything after scorer[0]
is unchanged and still sees the same activations.

This does not touch rl/. It builds the real module, runs both forms on the same
weights and inputs, and reports the max absolute difference.
"""
import torch

torch.manual_seed(0)
B, A, CTX, ENT, WIDTH = 256, 10, 384, 128, 256

scorer = torch.nn.Sequential(
    torch.nn.Linear(CTX + ENT, WIDTH), torch.nn.ReLU(), torch.nn.Linear(WIDTH, 1)
)
ctx = torch.randn(B, CTX)
entities = torch.randn(B, A, ENT)
slot_bias = torch.randn(A)

# --- current form -------------------------------------------------------
pairs = torch.cat([ctx.unsqueeze(1).expand(-1, A, -1), entities], dim=-1)
now = scorer(pairs).squeeze(-1) + slot_bias

# --- factored form ------------------------------------------------------
lin0 = scorer[0]
w_ctx, w_ent = lin0.weight[:, :CTX], lin0.weight[:, CTX:]
z = (torch.nn.functional.linear(ctx, w_ctx, lin0.bias).unsqueeze(1)
     + torch.nn.functional.linear(entities, w_ent))
h = scorer[1](z)
for layer in scorer[2:]:
    h = layer(h)
factored = h.squeeze(-1) + slot_bias

d = (now - factored).abs().max().item()
print(f"max |difference| over {B}x{A} logits: {d:.3e}")
print(f"relative to logit scale ({now.abs().max().item():.3f}): "
      f"{d / now.abs().max().item():.3e}")
print("EQUIVALENT" if d < 1e-4 else "NOT EQUIVALENT — do not ship")

# --- what it costs ------------------------------------------------------
now_mac = A * (CTX + ENT) * WIDTH + A * WIDTH
fac_mac = CTX * WIDTH + A * ENT * WIDTH + A * WIDTH
print(f"\nscorer[0] MAC/row: now {now_mac:,}  factored {fac_mac:,}  "
      f"cut {1 - fac_mac / now_mac:.1%}")

# --- and does it actually run faster at this shape? ---------------------
import time
def bench(fn, n=30):
    for _ in range(3):
        fn()
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t) / n

t_now = bench(lambda: scorer(torch.cat(
    [ctx.unsqueeze(1).expand(-1, A, -1), entities], dim=-1)).squeeze(-1) + slot_bias)
def fac():
    z = (torch.nn.functional.linear(ctx, w_ctx, lin0.bias).unsqueeze(1)
         + torch.nn.functional.linear(entities, w_ent))
    h = scorer[1](z)
    for layer in scorer[2:]:
        h = layer(h)
    return h.squeeze(-1) + slot_bias
t_fac = bench(fac)
print(f"forward only, B={B}: now {t_now*1e6:8.1f} us   factored {t_fac*1e6:8.1f} us"
      f"   {t_now/t_fac:.2f}x")
