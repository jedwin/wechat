cp /.tencentcloudbase/migrations/ /app/wxcloudrun/ -R
python3 manage.py makemigrations
python3 manage.py migrate
cp /app/wxcloudrun/migrations/ /.tencentcloudbase/ -R