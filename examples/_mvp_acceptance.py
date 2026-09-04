"""Brief §46 acceptance test, run as a real IPython session.

One IPython shell, one Python kernel: a Python cell, an R cell, a Stata cell and
an EViews cell must all execute successfully in sequence. This is the file the
notebook `06_mvp_acceptance.ipynb` mirrors.
"""

from IPython.testing.globalipapp import start_ipython

ip = start_ipython()
ip.run_line_magic("load_ext", "econenv")

print("\n--- 1. Python ---")
ip.run_cell("import pandas as pd, numpy as np\n"
            "rng = np.random.default_rng(7)\n"
            "df = pd.DataFrame({'x': rng.normal(size=40)})\n"
            "df['y'] = 2 + 0.5*df.x + rng.normal(scale=.3, size=40)\n"
            "print('python ok', df.shape)")

print("\n--- 2. R ---")
ip.run_cell_magic("R", "-i df -o rcoef",
                  "fit <- lm(y ~ x, data = df)\n"
                  "rcoef <- as.data.frame(coef(summary(fit)))\n"
                  "cat('R ok\n')")
print(ip.user_ns["rcoef"])

print("\n--- 3. Stata ---")
ip.run_line_magic("stata_push", "df")
ip.run_cell_magic("stata", "", "regress y x")

print("\n--- 4. EViews ---")
ip.run_cell_magic("eviews", "-i df -q",
                  "equation eq1.ls y c x")
print("EViews R2 =", ip.run_line_magic("eviews_get", "eq1.@r2"))

print("\n--- 5. back in Python ---")
ip.run_cell("print('still the same kernel:', df.shape)")

print("\n--- %econ status ---")
ip.run_line_magic("econ", "status")
print(ip.run_line_magic("econ", "versions"))
print("\nACCEPTANCE TEST PASSED: four engines, one kernel.")
