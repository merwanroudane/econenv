"""A searchable catalogue of GAUSS commands, for researchers.

GAUSS is the oldest language EconEnv drives and the least like the others. It
has no DataFrame in the pandas sense, its matrix syntax is its own, and the
things a researcher reaches for — ``ols``, ``vec``, ``sumc``, the ``~`` and
``|`` concatenation operators — are not guessable from a Python or R background.

So this catalogue is aimed at the specific question "how do I write that in
GAUSS", with a runnable line for each entry. ``verified`` marks the entries
resolved against a live GAUSS through EconEnv, so nothing here is asserted from
documentation alone.

``docs/engines/gauss-commands.md`` is generated from this module, so the page
and ``%econ gauss`` cannot drift apart.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

#: Library label meaning "part of the GAUSS language itself".
BASE = "GAUSS"


def _tick(verified: bool) -> str:
    """A check mark where the console can render one, ASCII where it cannot."""
    if not verified:
        return " "
    encoding = getattr(sys.stdout, "encoding", None) or "ascii"
    try:
        "✓".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return "*"
    return "✓"


@dataclass(frozen=True)
class Command:
    """One GAUSS command, described for someone doing applied econometrics."""

    name: str
    category: str
    does: str
    example: str
    library: str = BASE
    keywords: str = ""
    notes: str = ""
    verified: bool = False

    def __str__(self) -> str:
        lines = [f"{_tick(self.verified)} {self.name}", f"    {self.does}"]
        if self.library != BASE:
            lines.append(f"    needs: {self.library}")
        example = self.example.replace("\n", "\n         ")
        lines.append(f"    e.g. {example}")
        if self.notes:
            lines.append(f"    note: {self.notes}")
        return "\n".join(lines)


CATEGORIES: Dict[str, str] = {
    "basics": "Syntax, printing and the things that trip up newcomers",
    "matrix": "Building, shaping and slicing matrices",
    "algebra": "Linear algebra and solving systems",
    "stats": "Descriptive statistics and distributions",
    "data": "Reading and writing files and datasets",
    "clean": "Missing values, sorting, selecting and grouping",
    "regression": "Least squares and related estimators",
    "timeseries": "Lags, differences and time-series work",
    "optimize": "Optimisation and root finding",
    "control": "Loops, conditions and procedures",
    "random": "Random numbers and simulation",
    "output": "Controlling what GAUSS prints",
}

#: Libraries that are not part of base GAUSS.
CML = "CML / Constrained Maximum Likelihood"
TSMT = "TSMT (Time Series MT)"


COMMANDS: List[Command] = [
    # --------------------------------------------------------------- basics
    Command(
        "print",
        "basics",
        "Show a value. GAUSS prints nothing for a bare expression.",
        'print "rows: " rows(x);',
        keywords="show display output",
        notes="Unlike Python, `x;` on its own displays nothing.",
    ),
    Command(
        ";",
        "basics",
        "Every statement ends with a semicolon. A missing one is a syntax error.",
        "x = 5;",
        keywords="semicolon statement terminator",
    ),
    Command(
        "/* */",
        "basics",
        "A comment. `@ ... @` is the older form and also works.",
        "/* this is a comment */",
        keywords="comment remark note",
    ),
    Command(
        "let",
        "basics",
        "Build a matrix from literal values without expressions.",
        "let x = 1 2 3;",
        keywords="literal constant define",
    ),
    Command(
        "type",
        "basics",
        "What a symbol is: 6 is a matrix, 13 a string.",
        "print type(x);",
        keywords="class kind inspect",
        notes="EconEnv uses this to decide how a value crosses to Python.",
        verified=True,
    ),
    Command(
        "show",
        "basics",
        "List the symbols in the workspace with their sizes.",
        "show;",
        keywords="who whos workspace variables list",
    ),
    Command(
        "clear",
        "basics",
        "Remove symbols from the workspace.",
        "clear x, y;",
        keywords="delete remove reset",
    ),
    # --------------------------------------------------------------- matrix
    Command(
        "~",
        "matrix",
        "Horizontal concatenation — join matrices side by side.",
        "X = ones(rows(y),1) ~ x1 ~ x2;",
        keywords="cbind hstack concatenate columns bind",
        notes="This is how a design matrix with a constant is built.",
    ),
    Command(
        "|",
        "matrix",
        "Vertical concatenation — stack matrices on top of each other.",
        "z = a | b;",
        keywords="rbind vstack stack rows append",
    ),
    Command(
        "ones",
        "matrix",
        "A matrix of ones — the constant column of a regression.",
        "c = ones(rows(y), 1);",
        keywords="constant intercept fill",
        verified=True,
    ),
    Command(
        "zeros",
        "matrix",
        "A matrix of zeros.",
        "z = zeros(10, 3);",
        keywords="empty fill",
        verified=True,
    ),
    Command(
        "eye",
        "matrix",
        "The identity matrix.",
        "I = eye(3);",
        keywords="identity diagonal",
        verified=True,
    ),
    Command(
        "rows",
        "matrix",
        "Number of rows.",
        "n = rows(X);",
        keywords="length nobs count",
        verified=True,
    ),
    Command(
        "cols",
        "matrix",
        "Number of columns.",
        "k = cols(X);",
        keywords="width count",
        verified=True,
    ),
    Command(
        "reshape",
        "matrix",
        "Change the shape, filling row by row.",
        "B = reshape(A, 3, 4);",
        keywords="resize dimensions",
        verified=True,
    ),
    Command(
        "submat",
        "matrix",
        "Pull out chosen rows and columns.",
        "S = submat(X, 1|3, 2);",
        keywords="slice subset index",
        verified=True,
    ),
    Command(
        "delif",
        "matrix",
        "Delete rows where a condition holds.",
        "kept = delif(X, X[.,1] .< 0);",
        keywords="filter drop remove where",
        verified=True,
    ),
    Command(
        "selif",
        "matrix",
        "Keep rows where a condition holds.",
        "sub = selif(X, X[.,1] .> 0);",
        keywords="filter select where subset",
        verified=True,
    ),
    Command(
        "vec",
        "matrix",
        "Stack the columns into one long column vector.",
        "v = vec(A);",
        keywords="flatten ravel stack",
        notes="A GAUSS built-in, so a Python variable cannot be pushed under this name.",
        verified=True,
    ),
    Command(
        "vecr",
        "matrix",
        "Stack the rows instead of the columns.",
        "v = vecr(A);",
        keywords="flatten ravel rows",
        verified=True,
    ),
    Command(
        "diag",
        "matrix",
        "The diagonal of a matrix, as a column.",
        "d = diag(vc);",
        keywords="diagonal variance extract",
        verified=True,
    ),
    Command(
        "trimr",
        "matrix",
        "Drop rows from the top and bottom — how a lag is aligned.",
        "y_t = trimr(y, 1, 0);",
        keywords="lag trim drop align shift",
        verified=True,
    ),
    # -------------------------------------------------------------- algebra
    Command(
        "inv",
        "algebra",
        "Matrix inverse. Prefer / for solving a system.",
        "A_inv = inv(A);",
        keywords="inverse",
        notes="For least squares use y / X, which is more accurate than inv(X'X)X'y.",
        verified=True,
    ),
    Command(
        "invpd",
        "algebra",
        "Inverse of a positive definite matrix — faster and stabler.",
        "V = invpd(X'X);",
        keywords="inverse covariance cholesky",
        verified=True,
    ),
    Command(
        "/",
        "algebra",
        "Least squares solve: b = y / X solves X*b = y.",
        "b = y / X;",
        keywords="solve regression ols backslash divide",
        notes="The workhorse. This is GAUSS's equivalent of numpy.linalg.lstsq.",
    ),
    Command(
        "det",
        "algebra",
        "Determinant.",
        "d = det(A);",
        keywords="determinant singular",
        verified=True,
    ),
    Command(
        "rank",
        "algebra",
        "Numerical rank — how collinear the columns are.",
        "r = rank(X);",
        keywords="collinearity singular",
        verified=True,
    ),
    Command(
        "chol",
        "algebra",
        "Cholesky factor of a positive definite matrix.",
        "R = chol(S);",
        keywords="decomposition factor covariance",
        verified=True,
    ),
    Command(
        "eig",
        "algebra",
        "Eigenvalues.",
        "e = eig(A);",
        keywords="eigenvalue spectral",
        verified=True,
    ),
    Command(
        "eigv",
        "algebra",
        "Eigenvalues and eigenvectors together.",
        "{ e, v } = eigv(A);",
        keywords="eigenvector spectral decomposition",
        verified=True,
    ),
    Command(
        "svd",
        "algebra",
        "Singular values.",
        "s = svd(A);",
        keywords="decomposition pca",
        verified=True,
    ),
    Command(
        "'",
        "algebra",
        "Transpose, written as a trailing apostrophe.",
        "XX = X'X;",
        keywords="transpose",
    ),
    # ---------------------------------------------------------------- stats
    Command(
        "meanc",
        "stats",
        "Column means — returns one value per column.",
        "m = meanc(X);",
        keywords="average mean",
        verified=True,
    ),
    Command(
        "stdc",
        "stats",
        "Column standard deviations.",
        "s = stdc(X);",
        keywords="sd dispersion",
        verified=True,
    ),
    Command(
        "sumc", "stats", "Column sums.", "total = sumc(X);", keywords="total add", verified=True
    ),
    Command(
        "median",
        "stats",
        "Column medians.",
        "m = median(X);",
        keywords="middle quantile",
        verified=True,
    ),
    Command(
        "minc", "stats", "Column minima.", "lo = minc(X);", keywords="min smallest", verified=True
    ),
    Command(
        "maxc", "stats", "Column maxima.", "hi = maxc(X);", keywords="max largest", verified=True
    ),
    Command(
        "moment",
        "stats",
        "Cross-product matrix X'X, handling missing values.",
        "M = moment(X, 0);",
        keywords="crossproduct covariance",
        verified=True,
    ),
    Command(
        "corrx",
        "stats",
        "Correlation matrix.",
        "R = corrx(X);",
        keywords="correlation",
        verified=True,
    ),
    Command(
        "vcx", "stats", "Covariance matrix.", "V = vcx(X);", keywords="covariance", verified=True
    ),
    Command(
        "quantile",
        "stats",
        "Quantiles of each column.",
        "q = quantile(x, 0.5);",
        keywords="percentile median",
        verified=True,
    ),
    Command(
        "cdfn",
        "stats",
        "Standard normal CDF.",
        "p = cdfn(z);",
        keywords="normal probability",
        verified=True,
    ),
    Command(
        "cdftc",
        "stats",
        "Upper tail of the t distribution — the p-value of a t statistic.",
        "p = 2 * cdftc(abs(t), df);",
        keywords="pvalue significance t test",
        notes="Two-sided p-value is 2*cdftc(abs(t), df).",
        verified=True,
    ),
    Command(
        "cdftci",
        "stats",
        "Inverse t — the critical value for a confidence interval.",
        "crit = cdftci(0.025, df);",
        keywords="critical value interval",
        verified=True,
    ),
    Command(
        "cdfchic",
        "stats",
        "Upper tail of the chi-square distribution.",
        "p = cdfchic(stat, df);",
        keywords="chi square pvalue test",
        verified=True,
    ),
    Command(
        "cdffc",
        "stats",
        "Upper tail of the F distribution.",
        "p = cdffc(f, df1, df2);",
        keywords="f test pvalue",
        verified=True,
    ),
    # ----------------------------------------------------------------- data
    Command(
        "loadd",
        "data",
        "Load a dataset or CSV into a matrix or dataframe.",
        'X = loadd("data.csv");',
        keywords="read import csv open",
        verified=True,
    ),
    Command(
        "saved",
        "data",
        "Save a matrix as a GAUSS dataset or CSV.",
        'call saved(X, "out.csv", 0);',
        keywords="write export save",
        verified=True,
    ),
    Command(
        "csvReadM",
        "data",
        "Read a CSV straight into a matrix.",
        'X = csvReadM("data.csv");',
        keywords="read import csv",
        notes="What EconEnv uses to bring a DataFrame in.",
        verified=True,
    ),
    Command(
        "csvWriteM",
        "data",
        "Write a matrix to CSV.",
        'r = csvWriteM(X, "out.csv");',
        keywords="write export csv",
        notes="Writes about 15 significant digits; EconEnv writes 17 itself so a "
        "double round-trips exactly.",
        verified=True,
    ),
    Command(
        "save",
        "data",
        "Save a symbol to a .fmt (matrix) or .fst (string) file.",
        "save x;",
        keywords="persist store workspace",
        notes="How EconEnv carries values from one %%gauss cell to the next.",
    ),
    Command("load", "data", "Load a matrix saved with save.", "load x;", keywords="restore read"),
    Command(
        "loads",
        "data",
        "Load a *string* saved with save — load will not do it.",
        "loads name;",
        keywords="restore string",
    ),
    # ---------------------------------------------------------------- clean
    Command(
        "miss",
        "clean",
        "Turn values into GAUSS missing values.",
        "y = miss(y, -999);",
        keywords="missing na recode sentinel",
        verified=True,
    ),
    Command(
        "missex",
        "clean",
        "Set missing where a logical mask is true.",
        "y = missex(y, y .< 0);",
        keywords="missing na mask",
        verified=True,
    ),
    Command(
        "ismiss",
        "clean",
        "1 if the matrix contains any missing value.",
        'if ismiss(X); print "has gaps"; endif;',
        keywords="isna check missing",
        verified=True,
    ),
    Command(
        "packr",
        "clean",
        "Drop every row containing a missing value — listwise deletion.",
        "clean = packr(y ~ X);",
        keywords="dropna listwise complete cases",
        notes="Pack the y and X together so the same rows are dropped from both.",
        verified=True,
    ),
    Command(
        "sortc",
        "clean",
        "Sort rows by a chosen column, ascending.",
        "S = sortc(X, 1);",
        keywords="order arrange sort",
        verified=True,
    ),
    Command(
        "sortmc",
        "clean",
        "Sort by several columns.",
        "S = sortmc(X, 1|2);",
        keywords="order multiple sort",
        verified=True,
    ),
    Command(
        "unique",
        "clean",
        "The distinct values of a column, sorted.",
        "u = unique(g);",
        keywords="distinct levels groups",
        verified=True,
    ),
    Command(
        "counts",
        "clean",
        "How many elements fall in each bin — a frequency table.",
        "f = counts(x, breaks);",
        keywords="frequency histogram tabulate",
        verified=True,
    ),
    Command(
        "recode",
        "clean",
        "Replace values according to conditions.",
        "y = recode(y, y .> 100, 100);",
        keywords="replace winsorise cap",
        verified=True,
    ),
    # ----------------------------------------------------------- regression
    Command(
        "ols",
        "regression",
        "Least squares with standard errors, R-squared and sigma.",
        '{ vnam,m,b,stb,vc,se,sig,cx,rsq,resid,dw } = ols("", y, X);',
        keywords="regression least squares lm estimate",
        notes="Set __output=0 to suppress the printed report and _olsres=1 for residuals. "
        "EconEnv's compare_ols uses this.",
        verified=True,
    ),
    Command(
        "olsqr",
        "regression",
        "Least squares coefficients only, by QR — numerically safer.",
        "b = olsqr(y, X);",
        keywords="regression qr coefficients stable",
        verified=True,
    ),
    Command(
        "__output",
        "regression",
        "Set to 0 to stop ols printing its own report.",
        "__output = 0;",
        keywords="quiet suppress print output",
        notes="A global, set before calling ols.",
    ),
    Command(
        "_olsres",
        "regression",
        "Set to 1 to make ols return residuals and Durbin-Watson.",
        "_olsres = 1;",
        keywords="residuals durbin watson",
    ),
    Command(
        "glm",
        "regression",
        "Generalised linear models.",
        'call glm(y, X, "binomial");',
        keywords="logit probit poisson glm",
        verified=True,
    ),
    # ----------------------------------------------------------- timeseries
    Command(
        "lagn",
        "timeseries",
        "Lag a series by n periods.",
        "y1 = lagn(y, 1);",
        keywords="lag shift backward",
        verified=True,
    ),
    Command(
        "lag1",
        "timeseries",
        "Lag by one period.",
        "y1 = lag1(y);",
        keywords="lag shift",
        verified=True,
    ),
    Command(
        "diff",
        "timeseries",
        "First difference of a series.",
        "dy = y - lag1(y);",
        keywords="difference change growth",
        notes="Written with lag1; trim the first row before using it.",
    ),
    Command(
        "acf",
        "timeseries",
        "Sample autocorrelation function.",
        "a = acf(y, 12, 0);",
        keywords="autocorrelation correlogram lag acf",
        notes="acf(series, lags, order of differencing). Pass 1 as the third "
        "argument to difference first.",
        verified=True,
    ),
    Command(
        "pacf",
        "timeseries",
        "Sample partial autocorrelation function.",
        "p = pacf(y, 12, 0);",
        keywords="partial autocorrelation pacf lag order",
        notes="pacf(series, lags, order of differencing).",
        verified=True,
    ),
    Command(
        "dfgls",
        "timeseries",
        "DF-GLS unit root test.",
        "call dfgls(y, 1, 12);",
        library=TSMT,
        keywords="unit root stationarity dickey fuller",
        notes="Not resolvable on a machine without TSMT installed.",
    ),
    Command(
        "vmdiff",
        "timeseries",
        "Difference a matrix of series.",
        "d = vmdiff(Y, 1);",
        library=TSMT,
        keywords="difference stationarity",
        notes="Not resolvable on a machine without TSMT installed.",
    ),
    # ------------------------------------------------------------- optimize
    Command(
        "optmt",
        "optimize",
        "General unconstrained optimisation.",
        "out = optmt(&fn, start);",
        library=CML,
        keywords="minimise maximise optimise",
        notes="Not resolvable on a machine without CML installed.",
    ),
    Command(
        "qnewton",
        "optimize",
        "Quasi-Newton minimisation, in base GAUSS.",
        "{ x, f, g, ret } = qnewton(&fn, start);",
        keywords="minimise bfgs newton",
        verified=True,
    ),
    Command(
        "eqSolve",
        "optimize",
        "Solve a system of nonlinear equations.",
        "{ x, f, ret } = eqSolve(&fn, start);",
        keywords="root solve nonlinear",
        verified=True,
    ),
    Command(
        "gradp",
        "optimize",
        "Numerical gradient of a function.",
        "g = gradp(&fn, x0);",
        keywords="derivative jacobian gradient",
        verified=True,
    ),
    Command(
        "hessp",
        "optimize",
        "Numerical Hessian — the basis of a standard error.",
        "H = hessp(&fn, x0);",
        keywords="second derivative curvature",
        verified=True,
    ),
    # -------------------------------------------------------------- control
    Command(
        "proc",
        "control",
        "Define a procedure. Ends with endp.",
        "proc (1) = sqr(x);\n    retp(x .* x);\nendp;",
        keywords="function procedure define def",
        notes="The (1) is the number of values returned. A procedure must be defined "
        "in the same cell that uses it.",
    ),
    Command(
        "retp",
        "control",
        "Return values from a procedure.",
        "retp(b, se);",
        keywords="return output",
    ),
    Command(
        "local",
        "control",
        "Declare a procedure's local variables.",
        "local i, n, buf;",
        keywords="scope declare variables",
    ),
    Command(
        "do while",
        "control",
        "The loop. GAUSS has no for-in.",
        "i = 1;\ndo while i <= n;\n    i = i + 1;\nendo;",
        keywords="loop iterate while for repeat",
    ),
    Command(
        "do until",
        "control",
        "Loop until a condition becomes true.",
        "do until i > n;\n    i = i + 1;\nendo;",
        keywords="loop iterate until",
    ),
    Command(
        "if",
        "control",
        "Conditional. Needs endif, and elseif is one word.",
        'if x > 0;\n    print "positive";\nelseif x < 0;\n    print "negative";\nendif;',
        keywords="condition branch test",
    ),
    Command(
        ".*",
        "control",
        "Element-by-element multiply — `*` is matrix multiplication.",
        "z = x .* y;",
        keywords="elementwise hadamard multiply",
        notes="The dot prefix makes any operator elementwise: .* ./ .^ .> .==",
    ),
    # --------------------------------------------------------------- random
    Command(
        "rndn",
        "random",
        "Standard normal draws.",
        "e = rndn(100, 1);",
        keywords="normal gaussian random simulate",
        verified=True,
    ),
    Command(
        "rndu",
        "random",
        "Uniform draws on [0,1, verified=True).",
        "u = rndu(100, 1);",
        keywords="uniform random simulate",
    ),
    Command(
        "rndseed",
        "random",
        "Set the seed, so a simulation reproduces.",
        "rndseed 42;",
        keywords="seed reproducible replicate",
    ),
    Command(
        "rndKMn",
        "random",
        "Normal draws from an explicitly carried state.",
        "{ x, state } = rndKMn(100, 1, state);",
        keywords="normal reproducible stream",
        verified=True,
    ),
    # --------------------------------------------------------------- output
    Command(
        "format",
        "output",
        "Control how numbers print — width and decimals.",
        "format /rd 10,4;",
        keywords="print digits decimals width",
    ),
    Command(
        "output",
        "output",
        "Send printed output to a file as well as the screen.",
        "output file = log.txt on;",
        keywords="log file capture",
    ),
    Command(
        "printfm",
        "output",
        "Print a matrix with per-column formats.",
        'call printfm(X, 1~1, "*.*lf" ~ "*.*lf");',
        keywords="table format columns",
        verified=True,
    ),
    Command(
        "ftos",
        "output",
        "Format a number as a string.",
        'buf = ftos(x, "%*.*lf", 10, 4);',
        keywords="tostring format convert",
        notes="EconEnv uses this at 17 digits to move doubles without losing precision.",
        verified=True,
    ),
]


def categories() -> Dict[str, str]:
    """Category name to description."""
    return dict(CATEGORIES)


def by_category(name: str) -> List[Command]:
    """Every command in one category."""
    key = name.lower().strip()
    return [c for c in COMMANDS if c.category == key]


def get(name: str) -> Optional[Command]:
    """One command by exact name."""
    for command in COMMANDS:
        if command.name.lower() == name.lower().strip():
            return command
    return None


def find(term: str) -> List[Command]:
    """Commands matching a category, a name, or a word in the description."""
    needle = term.lower().strip()
    if not needle:
        return list(COMMANDS)
    if needle in CATEGORIES:
        return by_category(needle)

    scored = []
    for command in COMMANDS:
        haystack = " ".join(
            (command.name, command.does, command.keywords, command.category, command.notes)
        ).lower()
        if needle == command.name.lower():
            scored.append((0, command))
        elif needle in command.name.lower():
            scored.append((1, command))
        elif needle in command.keywords.lower():
            scored.append((2, command))
        elif needle in haystack:
            scored.append((3, command))
    return [c for _, c in sorted(scored, key=lambda pair: pair[0])]


def libraries() -> Dict[str, int]:
    """How many catalogued commands each library accounts for."""
    counts: Dict[str, int] = {}
    for command in COMMANDS:
        counts[command.library] = counts.get(command.library, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
