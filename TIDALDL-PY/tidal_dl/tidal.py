#!/usr/bin/env python
# -*- encoding: utf-8 -*-
'''
@File    :   tidal.py
@Time    :   2019/02/27
@Author  :   Yaron Huang 
@Version :   1.0
@Contact :   yaronhuang@qq.com
@Desc    :   Tidal API
'''
import os
import re
import json
import uuid
import requests

from aigpy import fileHelper
from aigpy import pathHelper
from aigpy import configHelper
from aigpy import netHelper
from aigpy import systemHelper
from pydub import AudioSegment

VERSION = '1.9.1'
URL_PRE = 'https://api.tidalhifi.com/v1/'
QUALITY = ['HI_RES', 'LOSSLESS', 'HIGH', 'LOW']
LOG = '''
 /$$$$$$$$ /$$       /$$           /$$               /$$ /$$
|__  $$__/|__/      | $$          | $$              | $$| $$
   | $$    /$$  /$$$$$$$  /$$$$$$ | $$          /$$$$$$$| $$
   | $$   | $$ /$$__  $$ |____  $$| $$ /$$$$$$ /$$__  $$| $$
   | $$   | $$| $$  | $$  /$$$$$$$| $$|______/| $$  | $$| $$
   | $$   | $$| $$  | $$ /$$__  $$| $$        | $$  | $$| $$
   | $$   | $$|  $$$$$$$|  $$$$$$$| $$        |  $$$$$$$| $$
   |__/   |__/ \_______/ \_______/|__/         \_______/|__/
   
       https://github.com/yaronzz/Tidal-Media-Downloader 
'''


class TidalTool(object):
    def __init__(self):
        self.config = TidalConfig()
        self.errmsg = ""

    def _get(self, url, params={}):
        retry = 3
        while retry > 0:
            retry -= 1
            try:
                self.errmsg = ""
                params['countryCode'] = self.config.countrycode
                resp = requests.get(
                    URL_PRE + url,
                    headers={'X-Tidal-SessionId': self.config.sessionid},
                    params=params).json()

                if 'status' in resp and resp['status'] == 404 and resp['subStatus'] == 2001:
                    self.errmsg = '{}. This might be region-locked.'.format(
                        resp['userMessage'])
                elif 'status' in resp and not resp['status'] == 200:
                    self.errmsg = '{}. Get operation err!'.format(
                        resp['userMessage'])
                    # self.errmsg = "Get operation err!"
                return resp
            except:
                if retry <= 0:
                    self.errmsg = 'Function `Http-Get` Err!'
                    return None

    def setTrackMetadata(self, track_info, file_path):
        path = pathHelper.getDirName(file_path)
        name = pathHelper.getFileNameWithoutExtension(file_path)
        exte = pathHelper.getFileExtension(file_path)
        tmpfile = path + '/' + name + 'TMP' + exte
        try:
            # 备份一下文件
            pathHelper.copyFile(file_path, tmpfile)
            # 设置信息
            ext = os.path.splitext(tmpfile)[1][1:]
            data = AudioSegment.from_file(tmpfile, ext)
            check = data.export(tmpfile, format=ext, tags={
                'Artist': track_info['artist']['name'],
                'Album': track_info['album']['title'],
                'Title': track_info['title'],
                'CopyRight': track_info['copyright'],
                'TrackNum': track_info['trackNumber']})
            # 检查文件大小
            if fileHelper.getFileSize(tmpfile) > 0:
                pathHelper.remove(file_path)
                pathHelper.copyFile(tmpfile, file_path)
        except:
            pass
        if os.access(tmpfile, 0):
            pathHelper.remove(tmpfile)

    def getStreamUrl(self, track_id, quality):
        return self._get('tracks/' + str(track_id) + '/streamUrl', {'soundQuality': quality})

    def getPlaylist(self, playlist_id):
        info = self._get('playlists/' + playlist_id)
        list = self.__getItemsList('playlists/' + playlist_id + '/items')
        return info, list

    def getAlbumTracks(self, album_id):
        return self._get('albums/' + str(album_id) + '/tracks')

    def getTrack(self, track_id):
        return self._get('tracks/' + str(track_id))

    def getAlbum(self, album_id):
        return self._get('albums/' + str(album_id))

    def getVideo(self, video_id):
        return self._get('videos/' + str(video_id))

    def getFavorite(self, user_id):
        trackList = self.__getItemsList(
            'users/' + str(user_id) + '/favorites/tracks')
        videoList = self.__getItemsList(
            'users/' + str(user_id) + '/favorites/videos')
        return trackList, videoList

    def __getItemsList(self, url):
        ret = self._get(url, {'limit': 0})
        count = ret['totalNumberOfItems']
        offset = 0
        limit = 100
        retList = None
        while offset < count:
            items = self._get(url, {'offset': offset, 'limit': limit})
            if self.errmsg != "":
                if self.errmsg.find('Too big page') >= 0:
                    limit = limit - 10
                    continue
                else:
                    return retList
            offset = offset + limit
            if retList == None:
                retList = items['items']
            else:
                retList.extend(items['items'])
        return retList

    def getTrackContributors(self, track_id):
        return self._get('tracks/' + str(track_id) + '/contributors')

    def getAlbumArtworkUrl(self, coverid, size=1280):
        return 'https://resources.tidal.com/images/{0}/{1}x{1}.jpg'.format(coverid.replace('-', '/'), size)

    def getVideoResolutionList(self, video_id):
        info = self._get('videos/' + str(video_id) + '/streamurl')
        if self.errmsg != "":
            return None

        content = netHelper.downloadString(info['url'], None)
        resolutionList, urlList = self.__parseVideoMasterAll(str(content))
        return resolutionList, urlList

    def getVideoMediaPlaylist(self, url):
        urlList = self.__parseVideoMediaPlaylist(url)
        return urlList

    def __parseVideoMasterAll(self, content):
        pattern = re.compile(r"(?<=RESOLUTION=).+?(?=\\n)")
        resolutionList = pattern.findall(content)
        pattern = re.compile(r"(?<=http).+?(?=\\n)")
        pList = pattern.findall(content)
        urlList = []
        for item in pList:
            urlList.append("http"+item)

        return resolutionList, urlList

    def __parseVideoMediaPlaylist(self, url):
        content = netHelper.downloadString(url, None)
        pattern = re.compile(r"(?<=http).+?(?=\\n)")
        plist = pattern.findall(str(content))
        urllist = []
        for item in plist:
            urllist.append("http"+item)
        return urllist

    def convertAlbumInfoToString(self, aAlbumInfo, aAlbumTracks):
        str = ""
        str += "[ID]          %d\n" % (aAlbumInfo['id'])
        str += "[Title]       %s\n" % (aAlbumInfo['title'])
        str += "[Artists]     %s\n" % (aAlbumInfo['artist']['name'])
        str += "[ReleaseDate] %s\n" % (aAlbumInfo['releaseDate'])
        str += "[SongNum]     %s\n" % (aAlbumInfo['numberOfTracks'])
        str += "[Duration]    %s\n" % (aAlbumInfo['duration'])
        str += '\n'

        i = 0
        while True:
            if i >= int(aAlbumInfo['numberOfVolumes']):
                break
            i = i + 1
            str += "===========Volume %d=============\n" % i
            for item in aAlbumTracks['items']:
                if item['volumeNumber'] != i:
                    continue
                str += '{:<8}'.format("[%d]" % item['trackNumber'])
                str += "%s\n" % item['title']
        return str

    def convertPlaylistInfoToString(seld, aPlaylistInfo, aTrackItems):
        str = ""
        str += "[Title]           %s\n" % (aPlaylistInfo['title'])
        str += "[Type]            %s\n" % (aPlaylistInfo['type'])
        str += "[NumberOfTracks]  %s\n" % (aPlaylistInfo['numberOfTracks'])
        str += "[NumberOfVideos]  %s\n" % (aPlaylistInfo['numberOfVideos'])
        str += "[Duration]        %s\n" % (aPlaylistInfo['duration'])

        i = 0
        str += "===========Track=============\n"
        for item in aTrackItems:
            type = item['type']
            item = item['item']
            if type != 'track':
                continue

            i = i + 1
            str += '{:<8}'.format("[%d]" % i) + item['title'] + '\n'

        i = 0
        str += "\n===========Video=============\n"
        for item in aTrackItems:
            type = item['type']
            item = item['item']
            if type != 'video':
                continue

            i = i + 1
            str += '{:<8}'.format("[%d]" % i) + item['title'] + '\n'

        return str

# LogIn and Get SessionID


class TidalAccount(object):
    def __init__(self, username, password, bymobile=False):
        token = '4zx46pyr9o8qZNRw'
        if bymobile:
            token = 'kgsOOmYk3zShYrNP'

        self.username = username
        self.token = token
        self.uuid = str(uuid.uuid4()).replace('-', '')[16:]
        self.errmsg = ""
        self.getSessionID(password)

    def getSessionID(self, password):
        postParams = {
            'username': self.username,
            'password': password,
            'token': self.token,
            'clientUniqueKey': self.uuid,
            'clientVersion': VERSION,
        }
        re = requests.post(URL_PRE + 'login/username', data=postParams).json()
        if 'status' in re:
            if re['status'] == 401:
                self.errmsg = "Uername or password err!"
            else:
                self.errmsg = "Get sessionid err!"
        else:
            self.session_id = re['sessionId']
            self.user_id = re['userId']
            self.country_code = re['countryCode']

            re = requests.get(URL_PRE + 'users/' + str(self.user_id),
                              params={'sessionId': self.session_id}).json()
            if 'status' in re and not re['status'] == 200:
                self.errmsg = "Sessionid is unvalid!"

# Config Tool


class TidalConfig(object):
    FILE_NAME = "tidal-dl.ini"

    def __init__(self):
        self.outputdir = configHelper.GetValue(
            "base", "outputdir", "./", self.FILE_NAME)
        self.sessionid = configHelper.GetValue(
            "base", "sessionid", "", self.FILE_NAME)
        self.countrycode = configHelper.GetValue(
            "base", "countrycode", "", self.FILE_NAME)
        self.quality = configHelper.GetValue(
            "base", "quality", "LOSSLESS", self.FILE_NAME)
        self.username = configHelper.GetValue(
            "base", "username", "", self.FILE_NAME)
        self.password = configHelper.GetValue(
            "base", "password", "", self.FILE_NAME)
        self.userid = configHelper.GetValue(
            "base", "userid", "", self.FILE_NAME)
        self.threadnum = configHelper.GetValue(
            "base", "threadnum", "3", self.FILE_NAME)

    def set_threadnum(self, threadnum):
        self.threadnum = threadnum
        configHelper.SetValue("base", "threadnum", threadnum, self.FILE_NAME)

    def set_outputdir(self, outputdir):
        self.outputdir = outputdir
        configHelper.SetValue("base", "outputdir", outputdir, self.FILE_NAME)

    def set_quality(self, quality):
        self.quality = quality
        configHelper.SetValue("base", "quality", quality, self.FILE_NAME)

    def set_account(self, username, password, sessionid, countrycode, userid):
        self.username = username
        self.password = password
        self.sessionid = sessionid
        self.countrycode = countrycode
        configHelper.SetValue("base", "username", username, self.FILE_NAME)
        configHelper.SetValue("base", "password", password, self.FILE_NAME)
        configHelper.SetValue("base", "sessionid", sessionid, self.FILE_NAME)
        configHelper.SetValue("base", "countrycode",
                              countrycode, self.FILE_NAME)
        configHelper.SetValue("base", "userid", str(userid), self.FILE_NAME)

    def valid_quality(self, quality):
        if quality in QUALITY:
            return True
        return False

    def valid_threadnum(self, threadnum):
        try:
            num = int(threadnum)
            return num > 0
        except:
            return False


# if __name__ == '__main__':
#     tool = TidalTool()
#     tool.getVideoStreamUrl(97246192)
