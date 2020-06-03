

CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"], show_all_commands_help_option_names=["-s", "--show_all"])

@click.group(cls=ShowAllGroup, context_settings=CONTEXT_SETTINGS)
def main():
  pass
  
# Use <main> --show_all/-s
