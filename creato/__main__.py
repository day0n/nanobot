"""Entry point: ``python -m creato`` starts the API server."""

import uvicorn


def main():
    from creato.api.server import build_app

    app = build_app()
    cfg = app.state.config
    uvicorn.run(app, host=cfg.api.host, port=cfg.api.port)


if __name__ == "__main__":
    main()
