cp /migrate_data/migrations/ /app/wxcloudrun/migrations/ -R
python3 manage.py makemigrations
python3 manage.py migrate
cp /app/wxcloudrun/migrations/ /migrate_data/migrations/ -R
