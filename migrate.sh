cp /migrate_data/migrations/ /app/wxcloudrun/ -R
python3 manage.py makemigrations
python3 manage.py migrate
cp /app/wxcloudrun/migrations/ /migrate_data/ -R
python3 manage.py runserver 0.0.0.0:80