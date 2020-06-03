import click
import sys
import copy

from click import HelpFormatter, wrap_text, Context, echo, Option


def measure_table(rows):
    widths = {}
    for row in rows:
        for idx, col in enumerate(row):
            widths[idx] = max(widths.get(idx, 0), len(col))
    return tuple(y for x, y in sorted(widths.items()))


def iter_rows(rows, col_count):
    for row in rows:
        row = tuple(row)
        yield row + ('',) * (col_count - len(row))


def iter_params_for_processing(invocation_order, declaration_order):
    """Given a sequence of parameters in the order as should be considered
    for processing and an iterable of parameters that exist, this returns
    a list in the correct order as they should be processed.
    """
    def sort_key(item):
        try:
            idx = invocation_order.index(item)
        except ValueError:
            idx = float('inf')
        return (not item.is_eager, idx)

    return sorted(declaration_order, key=sort_key)


def make_str(value):
    """Converts a value into a valid string."""
    if isinstance(value, bytes):
        return value.decode('utf-8', 'replace')
    return str(value)

# Not needed for now, Will be used in future
class ShowAllFormatter(click.HelpFormatter):

    def write_dl(self, rows, col_max=30, col_spacing=2):
        """Writes a definition list into the buffer.  This is how options
        and commands are usually formatted.

        :param rows: a list of two item tuples for the terms and values.
        :param col_max: the maximum width of the first column.
        :param col_spacing: the number of spaces between the first and
                            second column.
        """
        rows = list(rows)
        widths = measure_table(rows)
        """if len(widths) != 2:
            raise TypeError('Expected two columns for definition list')"""

        first_col = min(widths[0], col_max) + col_spacing
        # first_col = 19

        if not rows:
            return

        elif len(rows[0]) == 2:
            super().write_dl(rows=rows, col_max=col_max, col_spacing=col_spacing)
        
        elif len(rows[0]) == 3:
            for first, second, third in iter_rows(rows, len(widths)):
                first = "{}{}". format(first, third)
                self.write('%*s%s' % (self.current_indent, '', first))
                if not second:
                    self.write('\n')
                    continue
                if len(first) <= first_col - col_spacing:
                    self.write(' ' * (first_col - len(first)))
                else:
                    self.write('\n')
                    self.write(' ' * (first_col + self.current_indent))

                text_width = max(self.width - first_col - 2, 10)
                lines = iter(wrap_text(second, text_width).splitlines())
                if lines:
                    self.write(next(lines) + '\n')
                    for line in lines:
                        self.write('%*s%s\n' % (
                            first_col + self.current_indent, '', line))
                else:
                    self.write('\n')


class ShowAllMixin:

    def make_context(self, info_name, args, parent=None, **extra):
        """Same as BaseCommand.make_context but uses FeatureContext as con text class"""
        for key, value in self.context_settings.items():
            if key not in extra:
                extra[key] = value
        ctx = ShowAllContext(self, info_name=info_name, parent=parent, **extra)
        with ctx.scope(cleanup=False):
            self.parse_args(ctx, args)
        return ctx
    
    def get_show_all_commands_help_names(self, ctx):
        """Returns the names for the help option."""
        all_names = set(ctx.show_all_commands_help_option_names)
        for param in self.params:
            all_names.difference_update(param.opts)
            all_names.difference_update(param.secondary_opts)
        return all_names
    
    def get_show_all_commands_help_option(self, ctx):
        """Returns the help option object."""
        help_options = self.get_show_all_commands_help_names(ctx)
        
        # Add `add_show_all_commands` attribute to class
        """if not help_options or not self.add_help_option:
            return"""

        def show_all_commands_help(ctx, param, value):
            if value and not ctx.resilient_parsing:
                echo(self.show_all_commands(ctx), color=ctx.color)
                ctx.exit()
        return Option(help_options, is_flag=True,
                      is_eager=True, expose_value=False,
                      callback=show_all_commands_help,
                      help='Show this message and exit as help functionality.')
    
    def show_all_commands(self, ctx):
        formatter = ShowAllFormatter(width=ctx.terminal_width,
                            max_width=ctx.max_content_width)
        self.format_all_commands(ctx, formatter)
        return formatter.getvalue().rstrip('\n')
    
    def get_params(self, ctx):

        rv = super().get_params(ctx)
        show_all_commands_option = self.get_show_all_commands_help_option(ctx)
        if show_all_commands_option is not None:
            rv = rv + [show_all_commands_option]
        
        return rv
        
    def format_all_commands(self, ctx, formatter):
        
        # Use ctx.command_path to display from root to given command
        
        commands_queue = []
        commands_res_list = []

        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)

            if isinstance(cmd, ShowAllGroup):
                commands_queue.append([subcommand, cmd])
            else:
                commands_res_list.append([subcommand])

        while commands_queue:
            ele = commands_queue.pop(0)
            grp = ele.pop(len(ele) -1)

            for subcommand in grp.list_commands(ctx):
                cmd = grp.get_command(ctx, subcommand)

                if isinstance(cmd, ShowAllGroup):
                    ele_temp = copy.deepcopy(ele)
                    ele_temp.extend([subcommand, cmd])
                    commands_queue.append(ele_temp)
                else:
                    ele_temp = copy.deepcopy(ele)
                    ele_temp.append(subcommand)
                    commands_res_list.append(ele_temp)
        
        
        cmd_list = []
        for subcommand in commands_res_list:
            cmd_str = " ".join(subcommand)
            cmd_list.append(cmd_str)
        
        if len(cmd_list):
            limit = formatter.width - 6 - max(len(cmd) for cmd in cmd_list)

            rows = []
            for cmd_str in cmd_list:
                rows.append((cmd_str, ""))

            if rows:
                with formatter.section('Commands'):
                    formatter.write_dl(rows)

    def parse_args(self, ctx, args):

        if args:
            feature_help_names = self.get_show_all_commands_help_names(ctx)
            if args[0] in feature_help_names:
                param_order = [self.get_show_all_commands_help_option(ctx)]
                opts = {args[0]: True}
                
                for param in iter_params_for_processing(
                        param_order, self.get_params(ctx)):
                    value, args = param.handle_parse_result(ctx, opts, args)

                if args and not ctx.allow_extra_args and not ctx.resilient_parsing:
                    ctx.fail('Got unexpected extra argument%s (%s)'
                            % (len(args) != 1 and 's' or '',
                                ' '.join(map(make_str, args))))

                ctx.args = args
                rest = args

                if self.chain:
                    ctx.protected_args = rest
                    ctx.args = []
                elif rest:
                    ctx.protected_args, ctx.args = rest[:1], rest[1:]
        
        return super().parse_args(ctx, args)
            

class ShowAllContext(Context):

    def __init__(self, *args, **kwargs):

        global show_all_commands_option_names
        saco_names = kwargs.pop("show_all_commands_help_option_names", show_all_commands_option_names)
        show_all_commands_option_names = saco_names

        super().__init__(*args, **kwargs)
        if saco_names:
            self.show_all_commands_help_option_names = saco_names
    

class ShowAllGroup(ShowAllMixin, click.Group):
    """click Group that have -s/--show_all functionality enanbled"""

    pass
