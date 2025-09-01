# Meutch
Let's lend to each other

## Development

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

Default seeded login: `user1@example.com` / `password123`.

