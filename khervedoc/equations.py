"""Templated equation snippets grouped for the equation-builder palette.

Each entry is `(latex_template, preview)`. The latex template is what
the editor inserts at the cursor; the preview is what the palette
button shows. We use the literal box character (□) as a placeholder
inside templates so users can quickly tab through and replace each
slot with their own content.
"""
from __future__ import annotations


EQUATION_GROUPS: list[tuple[str, list[tuple[str, str]]]] = [
    ("Fractions & roots", [
        (r"\frac{\square}{\square}", "□/□"),
        (r"\tfrac{\square}{\square}", "small □/□"),
        (r"\dfrac{\square}{\square}", "display □/□"),
        (r"\sqrt{\square}", "√□"),
        (r"\sqrt[\square]{\square}", "ⁿ√□"),
        (r"\binom{\square}{\square}", "(□ □)"),
    ]),
    ("Sums, products, limits", [
        (r"\sum_{\square}^{\square} \square", "∑_□^□"),
        (r"\sum_{i=1}^{n} \square", "∑ᵢ₌₁ⁿ"),
        (r"\prod_{\square}^{\square} \square", "∏_□^□"),
        (r"\lim_{\square \to \square} \square", "lim_□→□"),
        (r"\liminf_{\square \to \square} \square", "lim inf"),
        (r"\limsup_{\square \to \square} \square", "lim sup"),
    ]),
    ("Integrals", [
        (r"\int_{\square}^{\square} \square \, d\square", "∫_□^□"),
        (r"\int \square \, d\square", "∫ □ d□"),
        (r"\iint_{\square} \square \, dA", "∬ dA"),
        (r"\iiint_{\square} \square \, dV", "∭ dV"),
        (r"\oint_{\square} \square \, d\square", "∮"),
        (r"\int_{-\infty}^{\infty} \square \, d\square", "∫_-∞^∞"),
    ]),
    ("Subscripts & superscripts", [
        (r"\square^{\square}", "x^□"),
        (r"\square_{\square}", "x_□"),
        (r"\square_{\square}^{\square}", "x_□^□"),
        (r"e^{\square}", "e^□"),
        (r"10^{\square}", "10^□"),
        (r"\square^{-1}", "x⁻¹"),
    ]),
    ("Derivatives", [
        (r"\frac{d\square}{d\square}", "d□/d□"),
        (r"\frac{d^{2}\square}{d\square^{2}}", "d²□/d□²"),
        (r"\frac{\partial \square}{\partial \square}", "∂□/∂□"),
        (r"\frac{\partial^{2} \square}{\partial \square^{2}}", "∂²□/∂□²"),
        (r"\nabla \square", "∇ □"),
        (r"\nabla^{2} \square", "∇² □"),
    ]),
    ("Greek inline", [
        (r"\alpha", "α"), (r"\beta", "β"), (r"\gamma", "γ"),
        (r"\Delta", "Δ"), (r"\theta", "θ"), (r"\lambda", "λ"),
        (r"\mu", "μ"), (r"\pi", "π"), (r"\sigma", "σ"),
        (r"\Sigma", "Σ"), (r"\phi", "φ"), (r"\omega", "ω"),
    ]),
    ("Vectors & matrices", [
        (r"\vec{\square}", "→x"),
        (r"\hat{\square}", "x̂"),
        (r"\bar{\square}", "x̄"),
        (r"\begin{pmatrix} \square & \square \\ \square & \square \end{pmatrix}", "(2×2)"),
        (r"\begin{bmatrix} \square & \square \\ \square & \square \end{bmatrix}", "[2×2]"),
        (r"\begin{vmatrix} \square & \square \\ \square & \square \end{vmatrix}", "|2×2|"),
    ]),
    ("Relations & operators", [
        (r"\square = \square", "□ = □"),
        (r"\square \approx \square", "□ ≈ □"),
        (r"\square \neq \square", "□ ≠ □"),
        (r"\square \leq \square", "□ ≤ □"),
        (r"\square \geq \square", "□ ≥ □"),
        (r"\square \propto \square", "□ ∝ □"),
        (r"\square \cdot \square", "□ · □"),
        (r"\square \times \square", "□ × □"),
    ]),
    ("Functions", [
        (r"\sin(\square)", "sin"),
        (r"\cos(\square)", "cos"),
        (r"\tan(\square)", "tan"),
        (r"\exp(\square)", "exp"),
        (r"\ln(\square)", "ln"),
        (r"\log_{\square}(\square)", "log"),
        (r"\arctan(\square)", "arctan"),
    ]),
    ("Display environments", [
        (r"\begin{equation}\n\square\n\end{equation}", "equation"),
        (r"\begin{align}\n\square &= \square \\\\\n\square &= \square\n\end{align}", "align"),
        (r"\begin{cases}\n\square & \text{if } \square \\\\\n\square & \text{otherwise}\n\end{cases}", "cases"),
    ]),
]


def all_templates() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for _, items in EQUATION_GROUPS:
        out.extend(items)
    return out
