# AssetAI backend deployment notes

## Render web service configuration

Use the repository's existing Python dependencies and start the ASGI app with
Uvicorn, binding to Render's assigned port:

- Build command: `pip install -r backend/requirements.txt`
- Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set these environment variables in the service configuration:

| Variable | Requirement |
| --- | --- |
| `ASSETAI_FRONTEND_ORIGIN` | The exact deployed frontend origin, such as `https://your-app.vercel.app`. Do not include a path or use `*`. Localhost origins remain available for development. |
| `ASSETAI_DB_ENGINE` | Required in production. Set to `sqlite` or `mysql`; the application does not add PostgreSQL support. |
| `ASSETAI_DB_PATH` | Optional SQLite file path. Defaults to `backend/app.db`. |

Render sets `RENDER=true`; deployments outside Render can set
`ASSETAI_ENV=production` to enable the same explicit database-engine check.
When using MySQL, configure the existing `ASSETAI_MYSQL_HOST`,
`ASSETAI_MYSQL_PORT`, `ASSETAI_MYSQL_USER`, `ASSETAI_MYSQL_PASSWORD`, and
`ASSETAI_MYSQL_DATABASE` variables. Keep database credentials and image-provider
tokens in the service's environment configuration, not in source control.

The backend uses opaque bearer session tokens stored in the selected database;
it does not require a JWT signing secret. Session and account durability depends
on the configured database. SQLite remains supported, but its database file
and other local files on a free Render web service's ephemeral filesystem do
not survive service replacement or restart.

## Runtime storage architecture and persistence

The current application stores files on the local filesystem:

| Data | Current location | Used for |
| --- | --- | --- |
| Uploaded originals and background-removed images | `backend/uploads/` | User uploads and intermediate image processing |
| Processed character images | `backend/app/processed/` | Inputs to animation generation |
| Generated character images | `backend/app/generated/` | Prompt-generated character assets |
| Animation frames | `backend/app/generated_frames/` | Generated frame sequences |
| Sprite sheets | `backend/app/sprite_sheets/` | Generated sprite-sheet assets |
| Generated videos | `backend/app/generated/videos/` | Animation provider output |

Uploads, processed/generated images, sprite sheets, and videos recorded as user
assets or history need persistent storage to remain downloadable and usable
after a service restart. Animation frames are intermediate generation outputs,
but are also written locally and are not durable on an ephemeral instance.
Dataset export and training files under `backend/data/` are separate from the
normal request-time asset flow.

No storage migration is implemented here. Before migrating, introduce a storage
abstraction with save, read, and delete operations, retaining the local
filesystem implementation and adding an S3-compatible implementation behind
the same interface. Keep user objects private and preserve the existing
owner-checked download and deletion behavior. Cloudflare R2 is one candidate
S3-compatible object-storage provider; review its current pricing, quotas, and
retention requirements before adopting it. No provider, bucket, credentials,
or paid service is configured by this change, and existing local files are not
moved or removed.
