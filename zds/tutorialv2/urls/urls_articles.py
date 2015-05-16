# coding: utf-8

from django.conf.urls import patterns, url

from zds.tutorialv2.views.views_published import ListArticles, DisplayOnlineArticle, DownloadOnlineArticle
from zds.tutorialv2.feeds import LastArticlesFeedRSS, LastArticlesFeedATOM

urlpatterns = patterns('',
                       # Flux
                       url(r'^flux/rss/$', LastArticlesFeedRSS(), name='feed-rss'),
                       url(r'^flux/atom/$', LastArticlesFeedATOM(), name='feed-atom'),

                       # View
                       url(r'^(?P<pk>\d+)/(?P<slug>.+)/$', DisplayOnlineArticle.as_view(), name='view'),

                       # downloads:
                       url(r'^(?P<pk>\d+)/(?P<slug>.+)\.md$',
                           DownloadOnlineArticle.as_view(requested_file='md'), name='download-md'),
                       url(r'^(?P<pk>\d+)/(?P<slug>.+)\.html$',
                           DownloadOnlineArticle.as_view(requested_file='html'), name='download-html'),
                       url(r'^(?P<pk>\d+)/(?P<slug>.+)\.pdf$',
                           DownloadOnlineArticle.as_view(requested_file='pdf'), name='download-pdf'),
                       url(r'^(?P<pk>\d+)/(?P<slug>.+)\.epub$',
                           DownloadOnlineArticle.as_view(requested_file='epub'), name='download-epub'),
                       url(r'^(?P<pk>\d+)/(?P<slug>.+)\.zip$',
                           DownloadOnlineArticle.as_view(requested_file='zip'), name='download-zip'),

                       # Listing
                       url(r'^$', ListArticles.as_view(), name='list'))
