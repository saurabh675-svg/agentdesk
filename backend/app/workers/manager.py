from .worker import Worker

WORKERS: dict[str, Worker] = {}


def _info(worker: Worker) -> dict:
    return {
        "type": worker.worker_type,
        "cli": worker.cli,
        "pid": worker._proc.pid if worker._proc else None,
        "alive": worker._proc.poll() is None if worker._proc else False,
        "tail": worker.tail_stdout(20),
    }


def _start(worker_type: str, cli: str, args: list[str] | None = None) -> dict:
    worker = Worker(worker_type, cli, args)
    try:
        worker.start()
    except Exception as exc:
        return {
            "type": worker_type,
            "cli": cli,
            "pid": None,
            "alive": False,
            "error": str(exc),
            "tail": [],
        }
    WORKERS[worker_type] = worker
    return _info(worker)


def create_cline(task: str | None = None) -> dict:
    return _start("cline", "cline", [task] if task else [])


def create_kiro(task: str | None = None) -> dict:
    return _start("kiro", "kiro.cmd")


def create_opencode(task: str | None = None) -> dict:
    return _start("opencode", "opencode.cmd", ["-m", task] if task else [])


def list_workers() -> list[dict]:
    return [_info(worker) for worker in WORKERS.values()]


def stop_worker(worker_type: str) -> dict:
    worker = WORKERS.get(worker_type)
    if worker:
        worker.stop()
    return {"ok": True, "stopped": worker_type}


def output_worker(worker_type: str) -> list[str]:
    worker = WORKERS.get(worker_type)
    return worker.tail_stdout(500) if worker else []
