PORT?=8000
run: migrate
	uv run python manage.py runserver ${PORT}

migrate:
	uv run python manage.py makemigrations
	uv run python manage.py migrate
push:
	git add . && git commit -m "push from makefile lenovo ubuntu" && git push origin main
superuser:
	uv run python manage.py createsuperuser