from __future__ import annotations

import uvicorn

if __name__ == "__main__":
    uvicorn.run("dimensional_gateway.server:app", host="127.0.0.1", port=8128, reload=False)
