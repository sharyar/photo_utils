import typer
from pathlib import Path
from utils import move_by_flag_and_copy_dir_structure

app = typer.Typer()


@app.command()
def remove_forked_files(target_dir: Path):
    if not target_dir.is_dir():
        return f"Invalid Dir: {target_dir}"

    junk_files = {
        'ds_store': [],
        'localized': [],
        'other_hidden': [],
        'forked_files': [],
    }


    for f in target_dir.rglob("*"):
        if f.is_file:
            match f.name:
                case '.DS_Store':
                    junk_files['ds_store'].append(f)
                case '.localized':
                    junk_files['localized'].append(f)
                case 'Thumbs.db':
                    junk_files['other_hidden'].append(f)
                case f if f.startswith("._"):
                    junk_files['forked_files'].append(f)
                case _:
                    pass

    print(f"Total count of files to be deleted: {sum(map(len, junk_files.values()))}")
    see_files: str = typer.prompt("Would you like to see the files or go ahead and delete them? S for see and D for delete")
    if see_files == "S":
        for l in junk_files.values():
            for f in l:
                print(type(f))
                print(f)
    # elif see_files == "D":
    #     for p in junk_files.values()


@app.command()
def move_files_by_flag(source_dir: str, flag: str, destination_dir: str):
    s = Path(source_dir)
    d = Path(destination_dir)
    move_by_flag_and_copy_dir_structure(source_dir=s, flag=flag, destination_dir=d)

if __name__ == "__main__":
    app()