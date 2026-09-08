"""``%%econlang`` — EconLang in a notebook cell.

The native magics stay exactly as they are (section 9 of the layer spec, section
44): this is additive. ``%%stata`` and the rest remain the escape hatch for
anything the language does not cover, and nothing about them changes.
"""

from __future__ import annotations

from typing import Any, Optional

from IPython.core.magic import Magics, cell_magic, magics_class, needs_local_scope

from ._common import MagicParser, shell_of, split_line


def _parser() -> MagicParser:
    parser = MagicParser(prog="%%econlang", add_help=False, description="Run an EconLang program.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the interpretation and the generated code without running anything.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        metavar="NAME",
        help="Bind the RunResult to this Python name.",
    )
    parser.add_argument(
        "--result", action="store_true", help="Return the RunResult instead of displaying it."
    )
    return parser


@magics_class
class EconLangMagics(Magics):
    """The language, in a cell."""

    @cell_magic("econlang")
    @needs_local_scope
    def econlang(
        self, line: str = "", cell: Optional[str] = None, local_ns: Optional[dict] = None
    ) -> Any:
        """Run EconLang.

        ::

            %%econlang
            data "macro.csv"

            set time:
                variable = year

            model ols baseline:
                y = gdp
                x = inflation, unemployment

            explain baseline
            show code baseline

        The estimated models are left in Python under the names they were given
        in the program, so ``baseline`` is a ``ModelResult`` afterwards and
        everything EconEnv already does with one — export, comparison — works
        on it unchanged.

        ``--dry-run`` reports the interpretation and the generated native code
        without loading data or starting an engine.
        """
        from .. import lang

        args = _parser().parse_args(split_line(line))
        result = lang.run(cell or "", dry_run=args.dry_run)

        shell = shell_of(self)
        # The models land in the user's namespace under their own names, which
        # is what makes the language a *layer* rather than a separate world.
        for name, model in result.models.items():
            shell.user_ns[name] = model
        if args.output:
            shell.user_ns[args.output] = result

        if args.result:
            return result

        print(result)
        for warning in result.diagnostics:
            print(f"\n{warning}")
        return None
