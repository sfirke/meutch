# Meutch

Meutch is a project that makes it easier for people to share items with each other. You can learn more about it, and actually share with people, at https://meutch.com/about.

This GitHub repo contains Meutch's source code. It's shared here for two reasons:
1. Transparency. Be reassured that indeed this is a project for the social good and it works as advertised.
2. Improvement. If you see a way to make Meutch better or more secure, please contribute it!

The theory of action is that Meutch is most effective when run as a single instance at https://www.meutch.com. Sam considered a decentralized, federated model but felt like the downsides outweighed the advantages. Ultimately, the most sharing would happen when everyone is on a single instance, and features are in place there (e.g., hidden circles) to make things safe for privacy-focused users.

Computer-savvy folks can pull this repo and deploy their own instances of Meutch for their communities. But this repo is focused on how to develop and contribute to this codebase.

## Development

*Pre-requisite: install docker compose. Meutch runs as a Python flask app but there's a Postgres database users for local development that deploys with docker compose.*

Start by cloning and pulling the repo to your machine. Set up a Python virtual environment in the `venv/` directory.

Run the development environment, database migrations, and (optionally) the development data seeder:

- Start the local Postgres container (if you use the test compose file):

```bash
docker compose -f docker-compose.test.yml up -d
```

- Prepare, migrate, seed, and run in one command:

```bash
./dev-start.sh seed
```

The `seed` argument is optional. Without it `./dev-start.sh` will prepare the environment and start the Flask server but will not run the data seeder.

- You can also run the steps manually:

```bash
export DATABASE_URL=postgresql://test_user:test_password@localhost:5433/meutch_dev
export FLASK_APP=app.py
export FLASK_ENV=development
source venv/bin/activate
flask db upgrade
flask seed data --env development
flask run
```

The dummy users seeded by the development data all have the same password. Login looks like:
Username: `user1@example.com` Password: `password123`.