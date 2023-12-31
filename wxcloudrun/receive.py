#!/usr/bin/env python
# -*- encoding: utf-8 -*-
"""
@File    :   receive.py
@Time    :   2019/8/6 10:15
@Author  :   Crisimple
@Github :    https://crisimple.github.io/
@Contact :   Crisimple@foxmail.com
@License :   (C)Copyright 2017-2019, Micro-Circle
@Desc    :   None
"""
import xml.etree.ElementTree as ET


def parse_xml(webData):
    if len(webData) == 0:
        return None

    xmlData = ET.fromstring(webData)
    msg_type = xmlData.find('MsgType').text

    if msg_type == 'text':
        return TextMsg(xmlData)
    elif msg_type == 'image':
        return ImageMsg(xmlData)
    elif msg_type == 'voice':
        return VoiceMsg(xmlData)
    elif msg_type == 'video':
        return VideoMsg(xmlData)
    elif msg_type == 'shortvideo':
        return ShortVideoMsg(xmlData)
    elif msg_type == 'event':
        return EventMsg(xmlData)



class Msg(object):
    def __init__(self, xmlData):
        self.ToUserName = xmlData.find('ToUserName').text
        self.FromUserName = xmlData.find('FromUserName').text
        self.CreateTime = xmlData.find('CreateTime').text
        self.MsgType = xmlData.find('MsgType').text
        # self.MsgId = xmlData.find('MsgId').text


class TextMsg(Msg):
    def __init__(self, xmlData):
        Msg.__init__(self, xmlData)
        self.Content = xmlData.find('Content').text.encode('utf-8')


class ImageMsg(Msg):
    def __init__(self, xmlData):
        Msg.__init__(self, xmlData)
        self.PicUrl = xmlData.find('PicUrl').text
        self.MediaId = xmlData.find('MediaId').text


class VoiceMsg(Msg):
    def __init__(self, xmlData):
        Msg.__init__(self, xmlData)
        self.MediaId = xmlData.find('MediaId').text
        self.Format = xmlData.find('Format').text


class VideoMsg(Msg):
    def __int__(self, xmlData):
        Msg.__init__(self, xmlData)

        self.MediaId = xmlData.find('MediaId').text
        self.ThumbMediaId = xmlData.find('ThumbMediaId').text


class ShortVideoMsg(Msg):
    def __int__(self, xmlData):
        Msg.__init__(self, xmlData)
        self.MediaId = xmlData.find('MediaId').text
        self.ThumbMediaId = xmlData.find('ThumbMediaId').text


class EventMsg(Msg):
    def __init__(self, xmlData):
        Msg.__init__(self, xmlData)
        self.Event = xmlData.find('Event').text
        
        if self.Event.lower() in ['click']:
            self.EventKey = xmlData.find('EventKey').text
        elif self.Event == 'location_select':
            self.Location_X = xmlData.find('SendLocationInfo/Location_X').text
            self.Location_Y = xmlData.find('SendLocationInfo/Location_Y').text
            self.Scale = xmlData.find('SendLocationInfo/Scale').text
            self.Label = xmlData.find('SendLocationInfo/Label').text
            self.Poiname = xmlData.find('SendLocationInfo/Poiname').text
        elif self.Event == 'LOCATION':
            self.Longitude = xmlData.find('Longitude').text
            self.Latitude = xmlData.find('Latitude').text
            self.Precision = xmlData.find('Precision').text
            

