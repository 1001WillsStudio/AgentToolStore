"""
Skills API handlers.

- GET    /api/skills              list
- POST   /api/skills              register single
- POST   /api/skills/folder       register folder
- POST   /api/skills/upload       browser upload
- DELETE /api/skills/<name>       remove
"""

from __future__ import annotations

import base64
import shutil
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

from ..config_manager import ConfigManager
from ..skill_manager import SkillDefinition, get_skill_manager
from ..skill_discovery import discover_skills
from .api_helpers import load_config, save_config

import logging
logger = logging.getLogger(__name__)


def list_skills() -> dict:
    """GET /api/skills"""
    cm = ConfigManager()
    cm.load()
    sm = get_skill_manager(cm.get_skill_dirs())
    sm.scan()
    result = {}
    for name, sd in sm._skills.items():
        result[name] = {
            "description": sd.description,
            "path": str(sd.skill_dir),
            "license": sd.license,
        }
    return result


def register_skill(body: dict) -> tuple[dict, int]:
    """POST /api/skills"""
    path = body.get("path", "").strip()
    if not path:
        return {"error": "path is required"}, 400

    skill_path = Path(path).expanduser().resolve()
    if not skill_path.is_dir():
        return {"error": f"Not a directory: {skill_path}"}, 400

    sd = SkillDefinition(skill_path)
    if not sd.load():
        return {"error": "Skill validation failed", "details": sd.errors}, 400

    cm = ConfigManager()
    cm.load()
    sm = get_skill_manager(cm.get_skill_dirs())
    installed = sm.install_skill(skill_path)
    if installed is None:
        return {"error": "Failed to install skill"}, 500

    for d in sm.skill_dirs:
        cm.add_skill_dir(str(d))

    cfg = load_config()
    cfg.setdefault("skills", {})[installed.name] = {
        "source": f"skill:{installed.name}",
        "enabled": True,
        "exposure": "secondary",
        "parallel_safe": False,
        "subagent_safe": False,
        "description": "",
    }
    save_config(cfg)

    return {"success": True, "skill": installed.name,
            "description": installed.description[:100],
            "path": str(skill_path)}, 200


def register_skill_folder(body: dict) -> tuple[dict, int]:
    """POST /api/skills/folder"""
    path = body.get("path", "").strip()
    if not path:
        return {"error": "path is required"}, 400
    fp = Path(path).expanduser().resolve()
    if not fp.is_dir():
        return {"error": f"Not a directory: {fp}"}, 400

    result = discover_skills(fp)
    if result.total == 0:
        return {"success": True, "registered": [],
                "failed": [], "message": "No SKILL.md directories found"}, 200

    cm = ConfigManager()
    cm.load()
    sm = get_skill_manager(cm.get_skill_dirs())

    registered = []
    failed = []
    for ds in result.valid_skills:
        try:
            sd = sm.install_skill(ds.skill_def.skill_dir)
            if sd:
                registered.append(sd.name)
            else:
                failed.append({"name": ds.name, "error": "install returned None"})
        except Exception as exc:
            failed.append({"name": ds.name, "error": str(exc)})

    for d in sm.skill_dirs:
        cm.add_skill_dir(str(d))

    cfg = load_config()
    for name in registered:
        cfg.setdefault("skills", {})[name] = {
            "source": f"skill:{name}", "enabled": True,
            "exposure": "secondary", "parallel_safe": False,
            "subagent_safe": False, "description": "",
        }
    save_config(cfg)

    return {"success": True, "registered": registered, "failed": failed,
            "total": result.total, "valid": result.valid_count,
            "invalid": result.invalid_count}, 200


def upload_skill(body: dict) -> tuple[dict, int]:
    """POST /api/skills/upload"""
    archive_b64 = body.get("archive", "")
    if not archive_b64:
        return {"error": "No 'archive' field in upload"}, 400

    try:
        zip_data = base64.b64decode(archive_b64)
    except Exception:
        logger.debug("Suppressed exception in api_skills.py", exc_info=True)
        return {"error": "Invalid base64 data"}, 400

    tmp = Path(tempfile.mkdtemp(prefix="toolstore-skill-"))
    try:
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            zf.extractall(tmp)

        result = discover_skills(tmp)
        if result.total == 0:
            return {"error": "No SKILL.md found in uploaded archive"}, 400

        cm = ConfigManager()
        cm.load()
        sm = get_skill_manager(cm.get_skill_dirs())

        registered = []
        failed = []
        for ds in result.valid_skills:
            try:
                installed = sm.install_skill(ds.skill_def.skill_dir)
                if installed:
                    registered.append(installed.name)
                else:
                    failed.append({"name": ds.name, "error": "install returned None"})
            except Exception as exc:
                failed.append({"name": ds.name, "error": str(exc)})

        for ds in result.invalid_skills:
            failed.append({"name": ds.name or str(ds.rel_path),
                           "error": "; ".join(ds.errors)})

        for d in sm.skill_dirs:
            cm.add_skill_dir(str(d))

        cfg2 = load_config()
        for name in registered:
            cfg2.setdefault("skills", {})[name] = {
                "source": f"skill:{name}", "enabled": True,
                "exposure": "secondary", "parallel_safe": False,
                "subagent_safe": False, "description": "",
            }
        save_config(cfg2)

        return {"success": True, "registered": registered, "failed": failed,
                "total": result.total, "valid": result.valid_count,
                "invalid": result.invalid_count}, 200
    except zipfile.BadZipFile:
        return {"error": "Uploaded file is not a valid zip archive"}, 400
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def remove_skill(name: str) -> tuple[dict, int]:
    """DELETE /api/skills/<name>"""
    cm = ConfigManager()
    cm.load()
    sm = get_skill_manager(cm.get_skill_dirs())
    sm.scan()

    sd = sm.get_skill(name)
    if not sd:
        return {"error": "Skill not found"}, 404

    skill_dir = sd.skill_dir
    if skill_dir.exists():
        shutil.rmtree(skill_dir, ignore_errors=True)

    sm._skills.pop(name, None)

    cfg = load_config()
    cfg.get("skills", {}).pop(name, None)
    save_config(cfg)
    return {"success": True}, 200
