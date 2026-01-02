```python
#!/usr/bin/env python3

"""
Drime CLI
Copyright (c) 2025 Drime

All rights reserved.
This software is licensed under the Drime License.
Unauthorized copying or usage is strictly prohibited.
"""

import argparse
import requests
import os
import math
import json
import re
import time
from typing import Optional, List
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from requests.exceptions import RequestException
import tempfile
import subprocess
import mimetypes

# Configuration
CONFIG_PATH = os.path.expanduser("~/.drimeconfig")
API_BASE_URL = "https://app.drime.cloud/api/v1"
CHUNK_SIZE = 25 * 1024 * 1024
BATCH_SIZE = 10
PART_UPLOAD_RETRIES = 3
HTTP_TIMEOUT = 30
console = Console()
version = "1.1.3"


def load_config():
    """Load the user configuration."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save the user configuration."""
    folder = os.path.dirname(CONFIG_PATH)
    if folder and not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)

def show_version():
    """Display CLI version."""
    console.print(f"[green]Drime CLI version:[/green] {version}")

def checkUpdate():
    """Check for CLI version updates (best-effort)."""
    try:
        response = requests.get("https://cli.drime.cloud/version", timeout=HTTP_TIMEOUT)
        if response.status_code == 200:
            remote_version = (response.text or "").strip()
            if remote_version and remote_version != version:
                console.print("[yellow]A new version of Drime CLI is available. Run `sudo drime update` to update the CLI client.[/yellow]")
        else:
            console.print("[red]Error checking for updates (non-200 response).[/red]")
    except RequestException:
        console.print("[red]Error checking for updates (network error).[/red]")


def get_api_key():
    """Retrieve the user's API key."""
    config = load_config()
    return config.get("api_key")


def api_request(method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
    """Make an API request with error handling and timeout."""
    api_key = get_api_key()
    if not api_key:
        console.print("[red]Error: API key not configured. Run `drime init`.[/red]")
        return None

    url = f"{API_BASE_URL}/{endpoint}"
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = requests.request(method, url, headers=headers, timeout=HTTP_TIMEOUT, **kwargs)
    except RequestException as e:
        console.print(f"[red]Network error while calling {endpoint}: {e}[/red]")
        return None

    if response.status_code == 401:
        console.print("[red]Error: Invalid API key.[/red]")
        return None
    elif response.status_code >= 400:
        try:
            message = response.json()
        except Exception:
            message = response.text
        console.print(f"[red]Error {response.status_code}: {message}[/red]")
        return None

    return response


def init():
    """Initialize the configuration and save the API key."""
    api_key = Prompt.ask("Enter your Drime API key").strip()
    save_config({"api_key": api_key})
    console.print("[green]API key successfully saved.[/green]")


def status():
    """Check if the API key is valid."""
    response = api_request("GET", "cli/loggedUser")
    if response:
        console.print("[green]API key valid and connection established successfully.[/green]")
        console.print("[green]Client version:[/green]", version)
        try:
            console.print("[green]Logged in as:[/green]", f"[blue]{response.json()['user']['email']}[/blue]")
        except Exception:
            console.print("[yellow]Could not parse user email from response.[/yellow]")


def update():
    """Update the CLI client."""
    if os.geteuid() != 0:
        console.print("[red]Error: You need to run this command with sudo.[/red]")
        return

    try:
        installer_resp = requests.get("https://cli.drime.cloud/install.sh", timeout=HTTP_TIMEOUT)
        if installer_resp.status_code != 200:
            console.print(f"[red]Error fetching installer (status {installer_resp.status_code}).[/red]")
            return

        fd, path = tempfile.mkstemp(prefix="drime_install_", suffix=".sh")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(installer_resp.content)
            os.chmod(path, 0o755)

            console.print("[green]Installer downloaded. Executing with sudo bash...[/green]")
            subprocess.run(["sudo", "bash", path], check=True)
            console.print("[green]Installer executed successfully.[/green]")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Installer failed: {e}[/red]")
            return
        except Exception as e:
            console.print(f"[red]Unexpected error running installer: {e}[/red]")
            return
        finally:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        return
    except RequestException as e:
        console.print(f"[red]Error fetching update: {e}[/red]")
        return

    if response.status_code == 200:
        try:
            with open("/usr/local/bin/drime", "w") as f:
                f.write(response.text)
            os.chmod("/usr/local/bin/drime", 0o755)
            console.print("[green]CLI client updated successfully.[/green]")
        except OSError as e:
            console.print(f"[red]Error writing updated CLI binary: {e}[/red]")
    else:
        console.print("[red]Error updating the CLI client (non-200 response).[/red]")


def upload_file(file_path: str, relative_path: str = "", workspace_id: int = 0):
    """Upload a file to Drime with optional relative path."""
    if not os.path.isfile(file_path):
        console.print(f"[red]File {file_path} does not exist.[/red]")
        return

    file_size = os.path.getsize(file_path)

    try:
        try:
            validate_payload = {
                "files": [
                    {
                        "name": os.path.basename(file_path),
                        "size": file_size,
                        "relativePath": relative_path,
                    }
                ],
                "workspaceId": workspace_id,
            }
            validate_resp = api_request("POST", "uploads/validate", json=validate_payload)
            duplicates = []
            if validate_resp:
                try:
                    vr = validate_resp.json()
                    duplicates = vr.get("duplicates", []) if isinstance(vr, dict) else []
                except Exception:
                    duplicates = []
        except Exception:
            duplicates = []

        if duplicates:
            do_for_all = False
            chosen_action = None
            for duplicate in duplicates:
                if not do_for_all:
                    chosen_action = Prompt.ask(
                        f"Duplicate detected for '{duplicate}'. Action",
                        choices=["rename", "replace", "cancel"],
                        default="rename",
                    )

                    apply_all = Prompt.ask("Apply this choice to all duplicates?", choices=["y", "n"], default="n")
                    do_for_all = apply_all.lower() == "y"

                if chosen_action == "cancel":
                    console.print("[yellow]Upload cancelled by user (duplicate conflict).[/yellow]")
                    return

                if chosen_action == "rename":
                    name_payload = {"name": duplicate, "workspaceId": workspace_id}
                    name_resp = api_request("POST", "entry/getAvailableName", json=name_payload)
                    new_folder_name = None
                    if name_resp:
                        try:
                            nr = name_resp.json()
                            new_folder_name = nr.get("available") if isinstance(nr, dict) else None
                        except Exception:
                            new_folder_name = None

                    if not new_folder_name:
                        console.print(f"[red]Could not find an available name for '{duplicate}'. Aborting upload.[/red]")
                        return

                    if relative_path:
                        relative_path = re.sub(rf"^{re.escape(duplicate)}", new_folder_name, relative_path)

                if chosen_action == "replace":
                    pass

        if file_size <= 30 * 1024 * 1024:
            return upload_simple(file_path, relative_path, workspace_id, new_folder_name if 'new_folder_name' in locals() else "")
        else:
            return upload_multipart(file_path, relative_path, workspace_id, new_folder_name if 'new_folder_name' in locals() else "")
    except KeyboardInterrupt:
        console.print("[yellow]Upload cancelled by user.[/yellow]")
        return
    except Exception as e:
        console.print(f"[red]Unexpected error during upload: {e}[/red]")
        return


def upload_multipart(file_path: str, relative_path: str, workspace_id: int, name: str = ""):
    """Upload a large file using multipart upload with robust handling."""
    file_name = name if name else os.path.basename(file_path)
    file_size = os.path.getsize(file_path)
    num_parts = math.ceil(file_size / CHUNK_SIZE)

    console.print(f"[yellow]Starting upload for {file_name} ({file_size} bytes)[/yellow]")

    mime_type = None
    try:
        import magic 
        try:
            mime_type = magic.from_file(file_path, mime=True)
        except Exception:
            mime_type = None
    except Exception:
        mime_type = None

    if not mime_type:
        mime_type, _ = mimetypes.guess_type(file_path)

    if not mime_type:
        mime_type = "application/octet-stream"

    init_response = api_request(
        "POST",
        "s3/multipart/create",
        json={
            "filename": file_name,
            "mime": mime_type,
            "size": file_size,
            "extension": os.path.splitext(file_name)[1].lstrip('.'),
            "relativePath": relative_path,
            "workspaceId": workspace_id,
        }
    )
    if not init_response:
        console.print("[red]Failed to initialize multipart upload.[/red]")
        return

    upload_data = init_response.json()
    upload_id = upload_data.get("uploadId")
    key = upload_data.get("key")

    if not upload_id or not key:
        console.print("[red]Invalid upload response: missing uploadId/key.[/red]")
        return

    uploaded_parts: List[dict] = []

    try:
        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "[progress.completed]{task.completed} of {task.total} bytes",
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("[yellow]Uploading parts...", total=file_size)

            with open(file_path, "rb") as f:
                part_number = 1
                while part_number <= num_parts:
                    batch_end = min(part_number + BATCH_SIZE - 1, num_parts)
                    batch_part_numbers = list(range(part_number, batch_end + 1))

                    sign_response = api_request(
                        "POST",
                        "s3/multipart/batch-sign-part-urls",
                        json={
                            "key": key,
                            "uploadId": upload_id,
                            "partNumbers": batch_part_numbers,
                        }
                    )
                    if not sign_response:
                        console.print(f"[red]Failed to sign parts {batch_part_numbers}.[/red]")
                        api_request("POST", "s3/multipart/abort", json={"key": key, "uploadId": upload_id})
                        return

                    urls_list = sign_response.json().get("urls")
                    if not urls_list or not isinstance(urls_list, list):
                        console.print(f"[red]No signed URLs returned for parts {batch_part_numbers}.[/red]")
                        api_request("POST", "s3/multipart/abort", json={"key": key, "uploadId": upload_id})
                        return

                    signed_urls = {u.get("partNumber"): u.get("url") for u in urls_list if "partNumber" in u and "url" in u}

                    for pn in batch_part_numbers:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break

                        signed_url = signed_urls.get(pn)
                        if not signed_url:
                            console.print(f"[red]No signed URL for part {pn}.[/red]")
                            api_request("POST", "s3/multipart/abort", json={"key": key, "uploadId": upload_id})
                            return

                        success = False
                        last_error = None
                        for attempt in range(1, PART_UPLOAD_RETRIES + 1):
                            try:
                                headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(chunk))}
                                part_response = requests.put(
                                    signed_url,
                                    data=chunk,
                                    headers=headers,
                                    timeout=HTTP_TIMEOUT
                                )
                            except RequestException as e:
                                last_error = e
                                console.print(f"[yellow]Attempt {attempt} failed for part {pn}: {e}. Retrying...[/yellow]")
                                time.sleep(1 * attempt)
                                continue

                            if part_response.status_code in (200, 201):
                                etag = part_response.headers.get("ETag", "").strip('"')
                                if not etag:
                                    console.print(f"[yellow]Warning: ETag missing for part {pn} (server returned {part_response.status_code}).[/yellow]")
                                uploaded_parts.append({
                                    "PartNumber": pn,
                                    "ETag": etag,
                                })
                                success = True
                                break
                            else:
                                last_error = f"Status {part_response.status_code}: {part_response.text}"
                                console.print(f"[yellow]Attempt {attempt} failed for part {pn}: {last_error}[/yellow]")
                                time.sleep(1 * attempt)

                        if not success:
                            console.print(f"[red]Failed to upload part {pn} after {PART_UPLOAD_RETRIES} attempts.[/red]")
                            api_request("POST", "s3/multipart/abort", json={"key": key, "uploadId": upload_id})
                            return

                        progress.update(task, advance=len(chunk))

                    part_number += BATCH_SIZE

        complete_response = api_request(
            "POST",
            "s3/multipart/complete",
            json={
                "key": key,
                "uploadId": upload_id,
                "parts": uploaded_parts,
            }
        )
        if not complete_response:
            console.print("[red]Failed to complete upload.[/red]")
            return

        entry_response = api_request(
            "POST",
            "s3/entries",
            json={
                "clientMime": mime_type,
                "clientName": file_name,
                "filename": key.split("/")[-1],
                "size": file_size,
                "clientExtension": os.path.splitext(file_name)[1].lstrip('.'),
                "relativePath": relative_path,
                "workspaceId": workspace_id,
            }
        )
        if not entry_response:
            console.print("[red]Failed to create file entry.[/red]")
            return

        entry_data = entry_response.json()
        if "fileEntry" in entry_data:
            file_info = entry_data["fileEntry"]
            console.print(f"[green]Upload upload completed:[/green] Name: {file_info.get('name')}, ID: {file_info.get('id')}")
        else:
            console.print("[red]No file entry returned.[/red]")

    except KeyboardInterrupt:
        console.print("[yellow]Upload cancelled by user (keyboard interrupt). Attempting to abort on server...[/yellow]")
        api_request("POST", "s3/multipart/abort", json={"key": key, "uploadId": upload_id})
        return
    except Exception as e:
        console.print(f"[red]Unexpected error during upload: {e}[/red]")
        api_request("POST", "s3/multipart/abort", json={"key": key, "uploadId": upload_id})
        return


def upload_simple(file_path: str, relative_path: str = "", workspace_id: int = 0, name: str = ""):
    """Upload a small file in a single request with progress indicator."""
    if not os.path.isfile(file_path):
        console.print(f"[red]File {file_path} does not exist.[/red]")
        return

    file_name = name if name else os.path.basename(file_path)
    full_relative_path = os.path.join(relative_path, file_name) if relative_path else file_name
    file_size = os.path.getsize(file_path)
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    try:
        with open(file_path, "rb") as file:
            with Progress(
                "[progress.description]{task.description}",
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                "[progress.completed]{task.completed} of {task.total} bytes",
                TimeElapsedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("[green]Uploading...", total=file_size)
                while True:
                    chunk = file.read(8192)
                    if not chunk:
                        break
                    progress.update(task, advance=len(chunk))

        with open(file_path, "rb") as file:
            response = api_request(
                "POST",
                "uploads",
                files={"file": (file_name, file, mime_type)},
                data={"relativePath": full_relative_path, "workspaceId": workspace_id},
            )
        if response:
            try:
                response_data = response.json()
                if "fileEntry" in response_data:
                    file_info = response_data["fileEntry"]
                    console.print(f"[green]File uploaded successfully:[/green] Name: {file_info.get('name')}, ID: {file_info.get('id')}")
                else:
                    console.print("[yellow]Upload succeeded but unexpected response structure.[/yellow]")
            except Exception:
                console.print("[yellow]Upload succeeded but failed to parse response.[/yellow]")
    except KeyboardInterrupt:
        console.print("[yellow]Upload cancelled by user.[/yellow]")
        return
    except RequestException as e:
        console.print(f"[red]Network error during upload: {e}[/red]")
        return
    except Exception as e:
        console.print(f"[red]Unexpected error during upload: {e}[/red]")
        return


def list_files(**filters):
    """List files with filtering options."""
    response = api_request("GET", "drive/file-entries", params=filters)
    if response:
        try:
            payload = response.json()
        except Exception:
            console.print("[red]Failed to parse response JSON.[/red]")
            console.print(response.text)
            return

        files = payload.get('data', [])
        if not filters.get("table"):
            console.print(json.dumps(payload, indent=2))
            return

        if files:
            table_view = Table(title="Files List", show_lines=True)
            table_view.add_column("ID", justify="right", style="cyan", no_wrap=True)
            table_view.add_column("Name", justify="left", style="green")
            table_view.add_column("Type", justify="center", style="magenta")
            table_view.add_column("Parent ID", justify="center", style="green")
            table_view.add_column("Hash", justify="center", style="blue")
            table_view.add_column("Workspace", justify="center", style="yellow")
            for file in files:
                table_view.add_row(
                    str(file.get('id')),
                    file.get('name', ''),
                    file.get('type', ''),
                    str(file.get('parent_id', '')),
                    file.get('hash', ''),
                    str(file.get('workspace_id', ''))
                )
            console.print(table_view)
        else:
            console.print("[yellow]No files found.[/yellow]")


def create_folder(name: str, parent_id: Optional[int] = None):
    """Create a folder in Drime."""
    data = {"name": name, "parentId": parent_id}
    response = api_request("POST", "folders", json=data)
    if response:
        try:
            folder_info = response.json()
            console.print(f"[green]Folder created successfully:[/green] Name: {folder_info.get('name')}, ID: {folder_info.get('id')}")
        except Exception:
            console.print("[yellow]Folder created but couldn't parse response.[/yellow]")


def rename_file(entry_id: str, new_name: str, description: Optional[str] = None):
    """Rename a file or add a description."""
    data = {"name": new_name}
    if description:
        data["description"] = description
    response = api_request("PUT", f"file-entries/{entry_id}", json=data)
    if response:
        console.print("[green]File successfully renamed.[/green]")


def delete_file(entry_ids: List[str], delete_forever: bool = False):
    """Delete one or more files."""
    data = {"entryIds": entry_ids, "deleteForever": delete_forever}
    response = api_request("POST", "file-entries/delete", json=data)
    if response:
        console.print("[green]File(s) deleted successfully.[/green]")


def download_file(hash_value: str):
    """Download a file from Drime."""
    response = api_request("GET", f"file-entries/download/{hash_value}", stream=True)
    if not response:
        return

    file_name = None
    content_disp = response.headers.get("Content-Disposition")
    if content_disp and "filename=" in content_disp:
        try:
            if "filename*" in content_disp:
                parts = content_disp.split("filename*=")
                file_name = parts[1].split(";")[0].strip().split("''")[-1]
            elif "filename=" in content_disp:
                parts = content_disp.split("filename=")
                file_name = parts[1].strip().strip('"').strip("'")
        except Exception:
            file_name = None

    if not file_name:
        file_name = f"drime_{hash_value}.zip"

    total_size = int(response.headers.get("Content-Length", 0))

    try:
        with open(file_name, "wb") as file:
            with Progress(
                "[progress.description]{task.description}",
                "[progress.percentage]{task.percentage:>3.0f}%",
                BarColumn(),
                "[progress.completed]{task.completed} of {task.total} bytes",
                TimeElapsedColumn(),
                TimeRemainingColumn(),
            ) as progress:
                task = progress.add_task("[green]Downloading...", total=total_size)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
                        progress.update(task, advance=len(chunk))

        console.print(f"[green]File downloaded successfully:[/green] {file_name}")
    except KeyboardInterrupt:
        console.print("[yellow]Download cancelled by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error while downloading file: {e}[/red]")


def share_file(entryId: int, **filters):
    """Share a file."""
    response = api_request("POST", f"file-entries/{entryId}/shareable-link")
    if response:
        try:
            if response.json().get('status') == "success":
                console.print(f"[green]Link successfully created:[/green]\n[blue]https://dri.me/{response.json()['link']['hash']}[/blue]")
            else:
                console.print("[red]An error occurred. Please try again later.[/red]")
        except Exception:
            console.print("[red]Failed to parse share response.[/red]")


def show_workspaces():
    """Show all workspaces."""
    response = api_request("GET", "me/workspaces")
    if response:
        try:
            workspaces = response.json().get('workspaces', [])
            if len(workspaces) == 0:
                console.print("[red]No workspaces found.[/red]")
            else:
                for workspace in workspaces:
                    console.print(f"[green]{workspace.get('name', '')}[/green]:\n - ID: {workspace.get('id')}\n - Role: {workspace.get('currentUser', {}).get('role_name')}\n - Owner: [blue]{workspace.get('owner', {}).get('email')}[/blue]\n\n")
        except Exception:
            console.print("[yellow]Couldn't parse workspaces response.[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="CLI client for Drime")
    parser.add_argument("-v", "--version", action="store_true", help="Show CLI version")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="Initialize the API key")
    subparsers.add_parser("status", help="Check connection status")
    subparsers.add_parser("update", help="Update the client")

    parser_add = subparsers.add_parser("add", help="Upload a file")
    parser_add.add_argument("file", type=str, help="File path")
    parser_add.add_argument("-p", "--path", type=str, default=None, help="Relative path to store the file (optional)")
    parser_add.add_argument("-w", "--workspace", type=int, default=0, help="Workspace ID (optional)")

    parser_ls = subparsers.add_parser("ls", help="List files")
    parser_ls.add_argument("-d", "--deleted", action="store_true", default=False, help="Show deleted files")
    parser_ls.add_argument("-s", "--starred", action="store_true", default=False, help="Show starred files")
    parser_ls.add_argument("-r", "--recent", action="store_true", default=False, help="Show recent files")
    parser_ls.add_argument("-S", "--shared", action="store_true", default=False, help="Show shared files")
    parser_ls.add_argument("-t", "--table", action="store_true", default=False, help="Display output in table format (default: JSON)")
    parser_ls.add_argument("-p", "--page", type=str, default=None, help="Display files in specified folder hash / page")
    parser_ls.add_argument("-w", "--workspace", type=int, default=0, help="Workspace ID")
    parser_ls.add_argument("-q", "--query", type=str, default=None, help="Search by name")
    parser_ls.add_argument("-T", "--type", type=str, choices=["folder", "image", "text", "audio", "video", "pdf"], default=None, help="Filter by file type")

    parser_mkdir = subparsers.add_parser("mkdir", help="Create a folder")
    parser_mkdir.add_argument("name", type=str)
    parser_mkdir.add_argument("-p", "--parent", dest="parentId", type=int, default=None, help="Parent folder ID (optional)")

    parser_rename = subparsers.add_parser("rename", help="Rename a file")
    parser_rename.add_argument("entry_id", type=str, help="File ID")
    parser_rename.add_argument("new_name", type=str, help="New file name")
    parser_rename.add_argument("-d", "--description", type=str, default=None, help="Description (optional)")

    parser_rm = subparsers.add_parser("rm", help="Delete a file")
    parser_rm.add_argument("entryIds", nargs='*', type=str, help="IDs of files to delete, separated by spaces")
    parser_rm.add_argument("-f", "--force", action="store_true", help="Delete permanently")

    parser_dl = subparsers.add_parser("get", help="Download a file")
    parser_dl.add_argument("hash", nargs='+', type=str, help="Hash(es) of the file(s) to download")

    parser_share = subparsers.add_parser("share", help="Share a file")
    parser_share.add_argument("entryId", type=int, help="ID of the file to share")
    parser_share.add_argument("-P", "--password", default=None, type=str, help="Add a password for the file")
    parser_share.add_argument("-e", "--expires", dest="expires_at", default=None, type=str, help="Define an expiration date for the link")
    parser_share.add_argument("-E", "--allow-edit", action="store_true", dest="allow_edit", help="Allow editing the file")
    parser_share.add_argument("-D", "--no-download", action="store_false", dest="allow_download", help="Disallow downloading the file (default: allow)")

    parser_work = subparsers.add_parser("workspaces", help="Show all workspaces")

    args = parser.parse_args()

    if getattr(args, "version", False):
        show_version() 
        return

    if args.command == "init":
        init()
    elif args.command == "status":
        status()
    elif args.command == "update":
        update()
    elif args.command == "add":
        upload_file(args.file, args.path if args.path else "", args.workspace)
    elif args.command == "ls":
        list_files(
            deletedOnly=args.deleted,
            starredOnly=args.starred,
            recentOnly=args.recent,
            sharedOnly=args.shared,
            table=args.table,
            workspaceId=args.workspace,
            query=args.query,
            type=args.type,
            pageId=args.page,
            folderId=args.page,
            backup=0
        )
    elif args.command == "mkdir":
        create_folder(args.name, args.parentId)
    elif args.command == "rename":
        rename_file(args.entry_id, args.new_name, args.description)
    elif args.command == "rm":
        if args.entryIds:
            delete_file(args.entryIds, args.force)
        else:
            console.print("[red]Error: No file IDs provided for deletion.[/red]")
    elif args.command == "get":
        for file_hash in args.hash:
            download_file(file_hash)
    elif args.command == "share":
        allow_download = getattr(args, "allow_download", True)
        share_file(args.entryId,
                   password=args.password,
                   expires_at=args.expires_at,
                   allow_edit=args.allow_edit,
                   allow_download=allow_download)
    elif args.command == "workspaces":
        show_workspaces()
    else:
        parser.print_help()

    if args.command != "update":
        checkUpdate()


if __name__ == "__main__":
    main()
```
