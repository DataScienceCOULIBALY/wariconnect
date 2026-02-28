web: python manage.py migrate && python manage.py collectstatic --noinput && python create_admin.py && gunicorn wariconnect.wsgi --bind 0.0.0.0:$PORT
