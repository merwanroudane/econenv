# FAQ

**Do I need all four programs?**
No. EconEnv works with any subset, including Python alone. A missing engine is
a warning in `doctor`, never an error.

**Does EconEnv include Stata or EViews?**
No. No binaries, no libraries, no licence files, no serial numbers. It finds
software already installed on your machine and drives it through each vendor's
documented automation interface. Licensing them is your responsibility.

**Why not a custom polyglot kernel?**
It would mean implementing the Jupyter messaging protocol and owning
completion, introspection, interrupt and display for four languages, against
four vendors' release schedules. An IPython extension gives the same
user-visible result for a fraction of the cost. It is re-evaluated in the
roadmap, not assumed away.

**EViews 14 has its own Jupyter kernel. Why not use it?**
`XeusEViews.exe` is a real kernel and it works — but it is a *separate* kernel,
so a notebook using it is an EViews notebook. That is the problem EconEnv
exists to solve.

**Why is `%%R` rpy2's magic and not yours?**
Because rpy2's is official and maintained. EconEnv loads it rather than shipping
a worse copy. `%%Rec` is always EconEnv's, and `%econ engines` tells you who
owns what.

**Why does EconEnv not require rpy2?**
rpy2 publishes no Windows wheels. Building the flagship R integration on a
package that will not install on the primary target platform would be a design
flaw. The subprocess backend is the default; rpy2 is used automatically where it
is available.

**Do I need `pyeviews`?**
No, and it does not currently work on modern Python — it imports `pkg_resources`
at module load, which setuptools removed. EconEnv talks to COM directly.

**Why does the same OLS give different AIC in each engine?**
Because they use different normalisations, all defensible. `compare_ols` shows
the numbers *and* names the reason. See [comparison.md](comparison.md).

**Can I run EViews on Linux?**
No. Automation is COM, which is Windows-only. Everything else works.

**Do the engines keep state between cells?**
Yes. All four are persistent sessions. `%econ restart <engine>` clears one.

**Is my data written to disk?**
Only where a transport requires it, into a private temp directory that is
deleted immediately. Stata transfer is fully in-memory; EViews goes through COM
arrays; R uses Arrow or a typed CSV handshake.

**Will `pystata` show up in `pip list`?**
No. It ships inside your Stata installation, not on PyPI. EconEnv puts
`<STATA_HOME>/utilities` on `sys.path` itself.

**Can I use EconEnv on a Jupyter server / in CI?**
Technically yes. Check your Stata and EViews licences first — they may restrict
concurrent sessions or server deployment. EconEnv does not and cannot police
that for you.

**Does anything get logged that shouldn't?**
No. The logger redacts anything matching a credential or serial-number pattern
before it reaches a record, and nothing executes unless you asked it to.

**Which estimators can I compare?**
OLS in v0.1. `%econ models` shows the full matrix with everything else marked
`planned` — the roadmap is visible rather than hidden.

**Why does `y ~ x1*x2` get rejected?**
Because it means different things in statsmodels, R, Stata and EViews. Building
the interaction column in Python first, or writing the command in that engine's
cell magic, is honest; a translation that quietly differs between programs is
not.

**How do I cite it?**
See [CITATION.cff](../CITATION.cff).
