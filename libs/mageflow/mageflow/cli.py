import click


@click.group()
def main():
    """Mageflow - Task orchestration framework"""
    pass


def register_commands():
    from mageflow.visualizer.commands import task_display

    main.add_command(task_display)


register_commands()
