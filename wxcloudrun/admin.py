from django.contrib import admin, messages
from django.utils.translation import ngettext
from wxcloudrun.models import *
from wxcloudrun.location_game import *
import os

errcode_file = 'errcode.csv'

# Register your models here.
class MenuButtonInline(admin.TabularInline):
    model = MenuButton


class SubButtonInline(admin.TabularInline):
    model = MenuSubButton


class MenuAdmin(admin.ModelAdmin):
    list_display = ('remark', 'app', 'menu_string')
    list_editable = ['app']
    inlines = [MenuButtonInline,]
    actions = ['update_menu', 'submit_menu']

    @admin.action(description='提交自定义菜单')
    def submit_menu(self, request, queryset):
        for obj in queryset:
            result, return_string = obj.save()  # MenuButton模型的save会自动更新json字符串
            if result:
                result, return_string = obj.submit_menu()  # 提交到腾讯服务器
                if result:
                    self.message_user(request, return_string, messages.SUCCESS)
                else:
                    self.message_user(request, return_string, messages.WARNING)
                    return False
            else:
                self.message_user(request, return_string, messages.WARNING)
                return False
        return True


class ButtonAdmin(admin.ModelAdmin):
    list_display = ('name', 'menu', 'type', 'key', 'url')
    inlines = [SubButtonInline, ]
    save_on_top = True


class MediaAdmin(admin.ModelAdmin):
    list_display = ('name', 'media_id', 'update_time', 'tags')
    list_filter = ('app', 'media_type')


class PlayerInline(admin.TabularInline):
    model = WechatPlayer


class MediaInline(admin.TabularInline):
    model = WechatMedia


class ExploreGameQuestInline(admin.TabularInline):
    model = ExploreGameQuest


class WechatPlayerAdmin(admin.ModelAdmin):
    list_display = ('open_id', 'nickname', 'app', 'cur_game_name', 'is_audit')
    list_editable = ['cur_game_name', 'is_audit']
    list_filter = ['app']
    # inlines = [GameDataInline,]
    actions = ['load_player_json_file']
    save_on_top = True

    @admin.action(description='加载用户游戏数据')
    def load_player_json_file(self, request, queryset):
        count = 0
        for obj in queryset:
            if obj.load_player_data():
                count += 1
        if count > 0:
            self.message_user(request, ngettext(
                f'{count} player data is created',
                f'{count} players data are created',
                count
            ), messages.SUCCESS)
        else:
            self.message_user(request, f'No player data is created', messages.WARNING)


class AppAdmin(admin.ModelAdmin):
    list_display = ('name', 'appid', 'image_count', 'video_count', 'subscriber_count')
    inlines = [PlayerInline, ]
    actions = ['get_subscriber_info', 'update_image', 'update_video', 'gen_new_passwd_obj']

    @admin.action(description='更新关注用户信息')
    def get_subscriber_info(self, request, queryset):
        for obj in queryset:
            result, return_string = obj.get_subscr_players()
            if result:
                # 如果成功，return_string会返回拉取到的关注用户数，以及更新成功和失败的用户数
                self.message_user(request, f'{return_string}', messages.SUCCESS)

            else:
                # 如果失败，return_obj会是失败原因字符串
                self.message_user(request, f'{return_string}', messages.WARNING)

    def update_media(self, request, queryset, media_type):
        total_count = 0
        for obj in queryset:
            count = obj.get_media_from_tencent(media_type)
            if count >= 0:
                total_count += count
            else:
                return count
        return total_count

    @admin.action(description='从腾讯服务器更新图片信息')
    def update_image(self, request, queryset):
        count = self.update_media(request, queryset, 'image')
        if count > 0:
            self.message_user(request, ngettext(
                f'{count} image updated',
                f'{count} images updated',
                count
            ), messages.SUCCESS)
        elif count == errcode_unkown_error:
            self.message_user(request, f'发生未知错误', messages.WARNING)
        elif count == errcode_access_token_refresh_failed:
            self.message_user(request, f'failed to refresh token', messages.WARNING)
        elif count == errcode_media_type_incorrect:
            self.message_user(request, f'media_type_incorrect', messages.WARNING)
        elif count == 0:
            self.message_user(request, f'No image in server', messages.WARNING)
        else:
            err_string = get_error_string(count)
            self.message_user(request, f'{err_string}：{count}', messages.WARNING)

    @admin.action(description='从腾讯服务器更新视频信息')
    def update_video(self, request, queryset):
        count = self.update_media(request, queryset, 'video')
        if count > 0:
            self.message_user(request, ngettext(
                f'{count} video updated',
                f'{count} videos updated',
                count
            ), messages.SUCCESS)
        elif count == errcode_unkown_error:
            self.message_user(request, f'发生未知错误', messages.WARNING)
        elif count == errcode_access_token_refresh_failed:
            self.message_user(request, f'failed to refresh access token', messages.WARNING)
        elif count == errcode_media_type_incorrect:
            self.message_user(request, f'media_type_incorrect', messages.WARNING)
        elif count == 0:
            self.message_user(request, f'No video resource in server', messages.WARNING)
        else:
            err_string = get_error_string(count)
            self.message_user(request, f'{err_string}：{count}', messages.WARNING)


class ErrorAutoReplyAdmin(admin.ModelAdmin):
    list_display = ('reply_content', 'reply_type', 'is_active')
    list_editable = ['reply_type',  'is_active']
    save_on_top = True


class AppKeywordAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'app', 'content_type', 'content_data')
    list_editable = ['app', 'content_type', 'content_data']
    list_filter = ['app']


class ExploreGameAdmin(admin.ModelAdmin):
    list_display = ['name', 'app', 'settings_file', 'is_active']
    list_editable = ['app', 'settings_file', 'is_active']
    list_filter = ['app']
    # inlines = [ExploreGameQuestInline]
    actions = ['export2csv', 'gen_new_passwd_obj']

    @admin.action(description='保存游戏配置')
    def export2csv(self, request, queryset):
        for obj in queryset:
            result_dict = obj.export_to_csv()
            result = result_dict['result']
            errmsg = result_dict['errmsg']
            if result:
                self.message_user(request, f'{errmsg}', messages.SUCCESS)
            else:
                self.message_user(request, f'{errmsg}', messages.WARNING)

    # @admin.action(description='导入游戏配置')
    # def import_from_csv(self, request, queryset):
    #     for obj in queryset:
    #         result_dict = obj.import_from_csv()
    #         result = result_dict['result']
    #         errmsg = result_dict['errmsg']
    #         if result:
    #             self.message_user(request, f'{errmsg}', messages.SUCCESS)
    #         else:
    #             self.message_user(request, f'{errmsg}', messages.WARNING)

    @admin.action(description='生成20个随机新密码')
    def gen_new_passwd_obj(self, request, queryset):
        for obj in queryset:
            result = obj.gen_passwords(how_many=20)
            if result > 0:
                # 如果成功
                self.message_user(request, f'已为{obj.name}生成{result}个新密码', messages.SUCCESS)
            else:
                # 生成失败，需要看docker的日志
                self.message_user(request, f'为{obj.name}生成密码失败，请查看docker的日志', messages.WARNING)


class ExploreGameQuestAdmin(admin.ModelAdmin):
    list_display = ['quest_trigger', 'prequire_list', 'reward_id']
    list_editable = ['prequire_list', 'reward_id']
    list_filter = ['game']


class PasswdAdmin(admin.ModelAdmin):
    list_display = ['password', 'game', 'assigned_player', 'is_assigned']
    list_editable = ['game', 'is_assigned']
    list_filter = ['game', 'is_assigned']


admin.site.register(WechatMenu, MenuAdmin)
admin.site.register(MenuButton, ButtonAdmin)
admin.site.register(WechatApp, AppAdmin)
admin.site.register(WechatMedia, MediaAdmin)
admin.site.register(WechatPlayer, WechatPlayerAdmin)
admin.site.register(ErrorAutoReply, ErrorAutoReplyAdmin)
admin.site.register(AppKeyword, AppKeywordAdmin)
admin.site.register(QqMap)
admin.site.register(ExploreGame, ExploreGameAdmin)
admin.site.register(ExploreGameQuest, ExploreGameQuestAdmin)
admin.site.register(WechatGamePasswd, PasswdAdmin)