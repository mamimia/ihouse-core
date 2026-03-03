import json
from core.db.validate_rebuild import snapshot_fingerprints

def _as_list(fp):
    if isinstance(fp, list):
        return fp
    if isinstance(fp, dict):
        out = []
        for k, v in fp.items():
            if isinstance(v, dict):
                row = {"table": k}
                row.update(v)
                out.append(row)
            else:
                out.append({"table": k, "sha256": str(v)})
        return out
    return [{"table": "unknown", "sha256": ""}]

def main():
    fp = snapshot_fingerprints()
    data = _as_list(fp)
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
