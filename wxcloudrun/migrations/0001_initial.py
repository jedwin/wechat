# Generated by Django 4.0.3 on 2022-04-05 12:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='ErrorAutoReply',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reply_type', models.CharField(choices=[('TEXT', '文字'), ('PIC', '图片')], default='文字', max_length=10)),
                ('reply_content', models.TextField(default='你输入的答案不对，请再想想')),
                ('is_active', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='ExploreGame',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('opening', models.TextField(blank=True, default='', max_length=1000, verbose_name='游戏启动内容')),
                ('settings_file', models.CharField(max_length=300)),
                ('is_active', models.BooleanField(default=False)),
                ('clear_requirement', models.CharField(blank=True, default='', max_length=100, verbose_name='本游戏通关条件，以｜分隔')),
                ('clear_notice', models.TextField(blank=True, default='', max_length=1000, verbose_name='本游戏通关提示内容')),
            ],
        ),
        migrations.CreateModel(
            name='MenuButton',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='', max_length=120, verbose_name='菜单标题')),
                ('type', models.CharField(choices=[('sub_button', '二级菜单'), ('click', '按钮'), ('view', '链接'), ('scancode_waitmsg', '扫码带提示'), ('scancode_push', '扫码推事件'), ('pic_sysphoto', '系统拍照发图'), ('pic_photo_or_album', '拍照或者相册发图'), ('pic_weixin', '微信相册发图'), ('location_select', '选择位置'), ('media_id', '图文消息'), ('view_limited', '图文消息（限制）'), ('article_id', '发布后的图文消息'), ('article_view_limited', '发布后的图文消息（限制）')], default='click', max_length=100)),
                ('key', models.CharField(blank=True, default='', max_length=100)),
                ('url', models.CharField(blank=True, default='', max_length=300)),
                ('media_id', models.CharField(blank=True, default='', max_length=100)),
                ('app_id', models.CharField(blank=True, default='', max_length=300, verbose_name='小程序id')),
                ('pagepath', models.CharField(blank=True, default='', max_length=300, verbose_name='小程序页面路径')),
                ('article_id', models.CharField(blank=True, default='', max_length=100)),
                ('sub_button', models.JSONField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='QqMap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(blank=True, default='', max_length=100)),
                ('key', models.CharField(blank=True, default='', max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='WechatApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('appid', models.CharField(max_length=100)),
                ('secret', models.CharField(max_length=100)),
                ('token', models.CharField(max_length=200)),
                ('acc_token', models.CharField(max_length=500)),
                ('name', models.CharField(max_length=100)),
                ('en_name', models.CharField(default='', max_length=100)),
                ('cur_game_name', models.CharField(default='', max_length=100)),
                ('super_user', models.CharField(max_length=200, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='WechatPlayer',
            fields=[
                ('name', models.CharField(blank=True, default='-', max_length=100)),
                ('open_id', models.CharField(default='', max_length=100, primary_key=True, serialize=False)),
                ('cur_game_name', models.CharField(blank=True, default='', max_length=100)),
                ('is_audit', models.BooleanField(default=False)),
                ('game_hist', models.JSONField(blank=True, null=True)),
                ('nickname', models.CharField(blank=True, default='', max_length=100)),
                ('remark', models.CharField(blank=True, default='', max_length=100)),
                ('subscribe_scene', models.CharField(blank=True, default='', max_length=100)),
                ('sex', models.IntegerField(blank=True, null=True)),
                ('tagid_list', models.CharField(blank=True, default='', max_length=200)),
                ('user_info', models.JSONField(blank=True, null=True)),
                ('subscribe', models.IntegerField(blank=True, default=0)),
                ('head_image', models.URLField(blank=True, default='', max_length=500)),
                ('cur_location', models.CharField(blank=True, default='', max_length=200)),
                ('cur_longitude', models.FloatField(blank=True, null=True)),
                ('cur_latitude', models.FloatField(blank=True, null=True)),
                ('cur_Precision', models.FloatField(blank=True, null=True)),
                ('poi_keyword', models.CharField(blank=True, default='', max_length=50, verbose_name='搜索兴趣点的关键词')),
                ('poi_dist', models.IntegerField(blank=True, default=100, verbose_name='搜索兴趣点的距离范围')),
                ('waiting_status', models.CharField(blank=True, default='', max_length=50)),
                ('app', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatapp')),
            ],
        ),
        migrations.CreateModel(
            name='WechatMenu',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('menu_string', models.JSONField(blank=True, null=True)),
                ('remark', models.CharField(blank=True, default='', max_length=100)),
                ('MatchRule', models.BooleanField(default=False)),
                ('match_tag_id', models.CharField(blank=True, default='', max_length=100)),
                ('app', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatapp')),
            ],
        ),
        migrations.CreateModel(
            name='WechatMedia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('media_id', models.CharField(max_length=100, null=True)),
                ('name', models.CharField(blank=True, max_length=200, null=True)),
                ('info', models.JSONField()),
                ('media_type', models.CharField(max_length=20, null=True)),
                ('app', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatapp')),
            ],
        ),
        migrations.CreateModel(
            name='WechatGamePasswd',
            fields=[
                ('password', models.CharField(max_length=50, primary_key=True, serialize=False)),
                ('is_assigned', models.BooleanField(default=False, verbose_name='是否已分配')),
                ('app', models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatapp')),
                ('assigned_player', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatplayer')),
            ],
        ),
        migrations.CreateModel(
            name='MenuSubButton',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='', max_length=120, verbose_name='菜单标题')),
                ('type', models.CharField(choices=[('click', '按钮'), ('view', '链接'), ('scancode_waitmsg', '扫码带提示'), ('scancode_push', '扫码推事件'), ('pic_sysphoto', '系统拍照发图'), ('pic_photo_or_album', '拍照或者相册发图'), ('pic_weixin', '微信相册发图'), ('location_select', '选择位置'), ('media_id', '图文消息'), ('view_limited', '图文消息（限制）'), ('article_id', '发布后的图文消息'), ('article_view_limited', '发布后的图文消息（限制）')], default='click', max_length=100)),
                ('key', models.CharField(blank=True, default='', max_length=100)),
                ('url', models.CharField(blank=True, default='', max_length=300)),
                ('media_id', models.CharField(blank=True, default='', max_length=100)),
                ('app_id', models.CharField(blank=True, default='', max_length=300, verbose_name='小程序id')),
                ('pagepath', models.CharField(blank=True, default='', max_length=300, verbose_name='小程序页面路径')),
                ('article_id', models.CharField(blank=True, default='', max_length=100)),
                ('parent_button', models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='wxcloudrun.menubutton')),
            ],
        ),
        migrations.AddField(
            model_name='menubutton',
            name='menu',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatmenu'),
        ),
        migrations.CreateModel(
            name='ExploreGameQuest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quest_trigger', models.CharField(default='', max_length=100, verbose_name='本题触发词')),
                ('prequire_list', models.CharField(blank=True, default='', max_length=1000, verbose_name='本题前置条件，以｜分隔，留空表示无需额外条件')),
                ('location_list', models.CharField(blank=True, default='', max_length=1000, verbose_name='限定位置关键词，以｜分隔，留空表示不限定位置')),
                ('poi_keyword', models.CharField(blank=True, default='', max_length=10, verbose_name='地点POI关键词，用于搜索用户周边')),
                ('question_type', models.CharField(choices=[('TEXT', '文字'), ('VIDEO', '视频'), ('PIC', '图片')], default='TEXT', max_length=10, verbose_name='谜面类型')),
                ('question_data', models.TextField(default='', max_length=1000, verbose_name='谜面')),
                ('hint_type', models.CharField(choices=[('TEXT', '文字'), ('VIDEO', '视频'), ('PIC', '图片')], default='TEXT', max_length=10, verbose_name='提示类型')),
                ('hint_data', models.TextField(blank=True, default='', max_length=1000, verbose_name='提示内容')),
                ('answer_list', models.CharField(default='', max_length=100, verbose_name='谜底列表，以｜分隔')),
                ('options_list', models.CharField(blank=True, default='', max_length=1000, verbose_name='谜底选项列表，以｜分隔，留空表示填空题')),
                ('reward_type', models.CharField(choices=[('TEXT', '文字'), ('VIDEO', '视频'), ('PIC', '图片')], default='TEXT', max_length=10, verbose_name='奖励类型')),
                ('reward', models.TextField(default='', max_length=1000, verbose_name='本题奖励内容')),
                ('reward_id', models.IntegerField(default=0, verbose_name='本题奖励id')),
                ('game', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.exploregame')),
            ],
        ),
        migrations.AddField(
            model_name='exploregame',
            name='app',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatapp'),
        ),
        migrations.CreateModel(
            name='AppKeyword',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('keyword', models.CharField(max_length=100, null=True)),
                ('content_type', models.CharField(choices=[('文字', '文字'), ('视频', '视频'), ('图片', '图片')], default='文字', max_length=100)),
                ('content_data', models.TextField(default='', max_length=1000)),
                ('app', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='wxcloudrun.wechatapp')),
            ],
        ),
    ]