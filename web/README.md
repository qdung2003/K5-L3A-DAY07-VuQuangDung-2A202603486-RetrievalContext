# Web demo

Start from the project root:

```powershell
.\.venv\Scripts\python.exe web/app.py
```

Open <http://127.0.0.1:8765>. **Saved trace** replays submitted traces without
API cost. **Live model** uses `.env` and can incur provider cost.

Choose **T02** for a sourced answer, **T-U02** for an abstention, and **Q01** for
the nested-loop evidence example. Click a citation to highlight its source;
the search tab also shows the exact context sent to the model. A replay displays
the original model time, rather than suggesting that a new model call occurred.

The server binds to localhost. Keep this demo local; it has no public-user accounts
or usage quotas. API credentials stay on the Python server and are never sent to
the browser. A different port is available with `--port 8766`.
