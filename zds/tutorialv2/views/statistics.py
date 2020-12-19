import uuid
from collections import defaultdict, OrderedDict, Counter
from datetime import timedelta, datetime, date
from json import loads

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils.translation import ugettext_lazy as _
from django.views.generic import FormView

import googleapiclient
from googleapiclient.discovery import build
from httplib2 import Http, ServerNotFoundError
from oauth2client.service_account import ServiceAccountCredentials

from zds.tutorialv2.forms import ContentCompareStatsURLForm, QuizzStatsForm
from zds.tutorialv2.mixins import SingleOnlineContentDetailViewMixin, SingleOnlineContentFormViewMixin
from zds.tutorialv2.models.quizz import QuizzUserAnswer, QuizzQuestion, QuizzAvailableAnswer
from zds.tutorialv2.utils import NamedUrl


class ContentQuizzStatistics(SingleOnlineContentFormViewMixin):
    form_class = QuizzStatsForm

    def post(self, request, *args, **kwargs):
        request.POST = loads(request.body)
        super(ContentQuizzStatistics, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        url = form.cleaned_data["url"]
        answers = {k: v for k, v in self.request.POST["result"].items()}
        resp_id = str(uuid.uuid4())
        for question, answers in answers.items():
            db_question = QuizzQuestion.objects.filter(question=question, url=url).first()
            if not db_question:
                db_question = QuizzQuestion(question=question, url=url)
                db_question.save()
            given_available_answers = self.request.POST["expected"][question]
            answers_labels = list(given_available_answers.keys())
            known_labels = QuizzAvailableAnswer.objects.filter(
                related_question=db_question, label__in=answers_labels
            ).values_list("label", flat=True)
            not_existing_answers = [l for l in answers_labels if l not in known_labels]
            QuizzAvailableAnswer.objects.exclude(label__in=answers_labels).filter(related_question=db_question).delete()

            for label in not_existing_answers:
                db_answer = QuizzAvailableAnswer(
                    related_question=db_question, label=label, is_good=given_available_answers[label]
                )
                db_answer.save()
            for answer in answers["labels"]:
                stat = QuizzUserAnswer(
                    related_content=self.object, related_question=db_question, full_answer_id=resp_id, answer=answer
                )
                stat.save()
        self.success_url = self.object.get_absolute_url_online()
        return super(ContentQuizzStatistics, self).form_valid(form)


class ContentStatisticsView(SingleOnlineContentDetailViewMixin, FormView):
    template_name = "tutorialv2/stats/index.html"
    form_class = ContentCompareStatsURLForm
    urls = []
    CACHE_PATH = str(settings.BASE_DIR / ".ga-api-cache")
    SCOPES = ["https://www.googleapis.com/auth/analytics.readonly"]
    DISCOVERY_URI = "https://analyticsreporting.googleapis.com/$discovery/rest"
    CLIENT_SECRETS_PATH = str(settings.BASE_DIR / "api_analytics_secrets.json")
    VIEW_ID = settings.ZDS_APP["stats_ga_viewid"]

    def post(self, request, *args, **kwargs):
        self.public_content_object = self.get_public_object()
        self.object = self.get_object()
        self.versioned_object = self.get_versioned_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["urls"] = [(named_url.url, named_url.name) for named_url in self.get_urls_to_render()]
        return kwargs

    def form_valid(self, form):
        self.urls = form.cleaned_data["urls"]
        return super().get(self.request)

    def get_urls_to_render(self):
        all_named_urls = self.get_content_urls()
        base_list = self.request.GET.getlist("urls", None) or self.urls
        if base_list:
            return [named_url for named_url in all_named_urls if named_url.url in base_list]
        else:
            return all_named_urls

    def get_content_urls(self):
        content = self.versioned_object
        urls = [NamedUrl(content.title, content.get_absolute_url_online(), 0)]
        if content.has_extracts():
            return urls
        for child in content.children:
            urls.append(NamedUrl(child.title, child.get_absolute_url_online(), 1))
            if not child.has_extracts():
                for subchild in child.children:
                    urls.append(NamedUrl(subchild.title, subchild.get_absolute_url_online(), 2))
        return urls

    def config_ga_credentials(self):
        try:
            credentials = ServiceAccountCredentials.from_json_keyfile_name(self.CLIENT_SECRETS_PATH, self.SCOPES)
            http = credentials.authorize(Http(cache=self.CACHE_PATH))
            analytics = build(
                "analytics", "v4", http=http, discoveryServiceUrl=self.DISCOVERY_URI, cache_discovery=False
            )
            return analytics
        except (ValueError, FileNotFoundError, ServerNotFoundError) as e:
            messages.error(
                self.request,
                _(
                    "Erreur de configuration de l'API Analytics. "
                    "Merci de contacter l'équipe des développeurs. « {} »"
                ).format(str(e)),
            )
            return None

    @staticmethod
    def get_ga_filters_from_urls(urls):
        filters = [{"operator": "EXACT", "dimensionName": "ga:pagePath", "expressions": u.url} for u in urls]
        return filters

    def get_cumulative_stats_by_url(self, urls, report):
        # Build an array of type arr[url] = {'pageviews': X, 'avgTimeOnPage': y}
        try:
            rows = report["data"]["rows"]
        except KeyError:
            messages.error(self.request, _("Aucune donnée de statistiques cumulées n'est disponible"))
            return []

        # Backfill data with zeroes
        data = {url.url: defaultdict(int) for url in urls}
        for r in rows:
            url = r["dimensions"][0]
            # avgTimeOnPage is convert to float then int to remove useless decimal part
            data[url] = {
                "pageviews": r["metrics"][0]["values"][0],
                "avgTimeOnPage": int(float(r["metrics"][0]["values"][1])),
                "users": r["metrics"][0]["values"][2],
                "newUsers": r["metrics"][0]["values"][3],
                "sessions": r["metrics"][0]["values"][4],
            }

        # Build the response array by matching NamedUrl and data[url]
        api_raw = [
            {
                "url": url,
                "pageviews": data[url.url].get("pageviews", 0),
                "avgTimeOnPage": data[url.url].get("avgTimeOnPage", 0),
                "users": data[url.url].get("users", 0),
                "newUsers": data[url.url].get("newUsers", 0),
                "sessions": data[url.url].get("sessions", 0),
            }
            for url in urls
        ]
        return api_raw

    def get_stats(self, urls, report, display_mode, start, end):
        try:
            rows = report["data"]["rows"]
        except KeyError:
            messages.error(self.request, _("Aucune donnée de statistiques détaillées n'est disponible"))
            return []

        api_raw = []
        metrics = [r["name"][3:] for r in report["columnHeader"]["metricHeader"]["metricHeaderEntries"]]

        period = (end - start).days

        data = {}
        if display_mode in ("global", "details"):
            # Prepare empty val list (backfill with zeros for missing dates)
            for i in range(period + 1):
                day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
                data[day] = {m: 0 for m in metrics}
            # Fill in data
            for r in rows:
                data_date = r["dimensions"][0]
                data_date = "{}-{}-{}".format(data_date[0:4], data_date[4:6], data_date[6:8])
                for i, m in enumerate(metrics):
                    data[data_date][m] = r["metrics"][0]["values"][i]

            stats = {}
            for i, m in enumerate(metrics):
                stats[m] = []
                for d in data:
                    stats[m].append({"date": d, m: data[d][m]})
                stats[m] = sorted(stats[m], key=lambda k: k["date"])
            api_raw = [{"label": _("Global"), "stats": stats}]
        else:

            data = {}

            for url in urls:
                data[url.url] = {"stats": {}}
                # Prepare empty val list (backfill with zeros for missing dates)
                for i in range(period + 1):
                    day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
                    data[url.url]["stats"][day] = defaultdict(int)

            for r in rows:
                url = r["dimensions"][1]
                data_date = r["dimensions"][0]
                data_date = "{}-{}-{}".format(data_date[0:4], data_date[4:6], data_date[6:8])

                for i, m in enumerate(metrics):
                    data[url]["stats"][data_date][m] = r["metrics"][0]["values"][i]

            for url in urls:
                stats = {}
                for i, m in enumerate(metrics):
                    stats[m] = []
                    for d in data[url.url]["stats"]:
                        stats[m].append({"date": d, m: data[url.url]["stats"][d].get(m, 0)})
                    stats[m] = sorted(stats[m], key=lambda k: k["date"])
                element = {"label": url.name, "stats": stats}
                api_raw.append(element)
        return api_raw

    def get_simple_stat(self, report, info):
        try:
            rows = report["data"]["rows"]
        except KeyError:
            messages.error(self.request, _("Aucune donnée n'est disponible (métrique « {} »)").format(info))
            return []
        api_raw = OrderedDict()
        for r in rows:
            api_raw[r["dimensions"][0]] = r["metrics"][0]["values"][0]
        return api_raw

    def get_referrer_stats(self, report):
        return self.get_simple_stat(report, "referrer")

    def get_keyword_stats(self, report):
        return self.get_simple_stat(report, "keyword")

    def get_all_stats(self, urls, start, end, display_mode):
        # nb_days = (end - start).days
        analytics = self.config_ga_credentials()
        if not analytics:
            return ([], [], [], [])

        # Filters to get all needed pages only
        filters = self.get_ga_filters_from_urls(urls)
        date_ranges = {"startDate": start.strftime("%Y-%m-%d"), "endDate": end.strftime("%Y-%m-%d")}

        metrics = [
            {"expression": "ga:pageviews"},
            {"expression": "ga:avgTimeOnPage"},
            {"expression": "ga:users"},
            {"expression": "ga:newUsers"},
            {"expression": "ga:sessions"},
        ]

        table_data_report = {
            "viewId": self.VIEW_ID,
            "dateRanges": date_ranges,
            "metrics": metrics,
            "dimensions": [{"name": "ga:pagePath"}],
            "dimensionFilterClauses": [{"filters": filters}],
        }

        referrer_report = {
            "viewId": self.VIEW_ID,
            "dateRanges": date_ranges,
            "metrics": [{"expression": "ga:visits"}],
            "dimensions": [{"name": "ga:fullReferrer"}],
            "orderBys": [{"fieldName": "ga:visits", "sortOrder": "DESCENDING"}],
            "dimensionFilterClauses": [{"filters": filters}],
        }

        keyword_report = {
            "viewId": self.VIEW_ID,
            "dateRanges": date_ranges,
            "metrics": [{"expression": "ga:visits"}],
            "dimensions": [{"name": "ga:keyword"}],
            "orderBys": [{"fieldName": "ga:visits", "sortOrder": "DESCENDING"}],
            "dimensionFilterClauses": [{"filters": filters}],
        }

        if display_mode in ("global", "details"):
            # Find level 0 url
            if display_mode == "global":
                target_url = [u for u in urls if u.level == 0]
                filters = [
                    {"operator": "BEGINS_WITH", "dimensionName": "ga:pagePath", "expressions": target_url[0].url}
                ]
            else:
                target_url = [urls[0]]
                filters = self.get_ga_filters_from_urls(target_url)

        dimensions = [{"name": "ga:date"}]
        if display_mode == "comparison":
            dimensions.append({"name": "ga:pagePath"})
        graphs_data_report = {
            "viewId": self.VIEW_ID,
            "dateRanges": date_ranges,
            "metrics": metrics,
            "dimensions": dimensions,
            "dimensionFilterClauses": [{"filters": filters}],
        }

        try:
            response = (
                analytics.reports()
                .batchGet(
                    body={"reportRequests": [graphs_data_report, table_data_report, referrer_report, keyword_report]}
                )
                .execute()
            )
        except googleapiclient.errors.HttpError as e:
            messages.error(
                self.request,
                _("Un problème a eu lieu lors de la requête vers l'API Google Analytics. « {} »").format(e),
            )
            return ([], [], [], [])

        return (
            self.get_stats(urls, response["reports"][0], display_mode, start, end),
            self.get_cumulative_stats_by_url(urls, response["reports"][1]),
            self.get_referrer_stats(response["reports"][2]),
            self.get_keyword_stats(response["reports"][3]),
        )

    def get_start_and_end_dates(self):
        end_date = self.request.GET.get("end_date", None)
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except TypeError:
            end_date = date.today()
        except ValueError:
            end_date = date.today()
            messages.error(self.request, _("La date de fin fournie est invalide."))

        start_date = self.request.GET.get("start_date", None)
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except TypeError:
            start_date = end_date - timedelta(days=7)
        except ValueError:
            start_date = end_date - timedelta(days=7)
            messages.error(self.request, _("La date de début fournie est invalide."))

        if start_date > end_date:
            end_date, start_date = start_date, end_date

        return start_date, end_date

    def get_display_mode(self, urls):
        # TODO make display_mode an enum ?
        # Good idea, but not straightforward for the template integration
        if len(urls) == 1:
            return "details"
        if len(urls) == len(self.get_content_urls()):
            return "global"
        return "comparison"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not (self.is_author or self.is_staff):
            raise PermissionDenied

        urls = self.get_urls_to_render()
        start_date, end_date = self.get_start_and_end_dates()
        display_mode = self.get_display_mode(urls)
        all_stats = self.get_all_stats(urls, start_date, end_date, display_mode)
        quizz_stats = {}
        base_questions = list(
            QuizzUserAnswer.objects.filter(
                date_answer__range=(start_date, end_date), related_content__pk=self.object.pk
            ).values_list("related_question", flat=True)
        )
        total_per_question = list(
            QuizzUserAnswer.objects.values("related_question__pk")
            .filter(related_question__pk__in=base_questions, date_answer__range=(start_date, end_date))
            .annotate(nb=Count("full_answer_id"))
        )
        total_per_question = {a["related_question__pk"]: a["nb"] for a in total_per_question}
        total_per_label = list(
            QuizzUserAnswer.objects.values(
                "related_question__pk", "related_question__question", "related_question__url", "answer"
            )
            .filter(related_question__in=base_questions, date_answer__range=(start_date, end_date))
            .annotate(nb=Count("answer"))
        )

        for base_question in set(base_questions):
            full_answers_total = {}
            url = ""
            question = ""
            for available_answer in (
                QuizzAvailableAnswer.objects.filter(related_question__pk=base_question)
                .prefetch_related("related_question")
                .all()
            ):
                full_answers_total[available_answer.label] = {"good": available_answer.is_good, "nb": 0}
                url = available_answer.related_question.url
                question = available_answer.related_question.question
                for r in total_per_label:
                    if (
                        r["related_question__pk"] == base_question
                        and r["answer"].strip() == available_answer.label.strip()
                    ):
                        full_answers_total[available_answer.label]["nb"] = r["nb"]
            if url not in quizz_stats:
                quizz_stats[url] = OrderedDict()
            quizz_stats[url][question] = {"total": total_per_question[base_question], "responses": full_answers_total}
        context.update(
            {
                "display": display_mode,
                "urls": urls,
                "stats": all_stats[0],  # Graph
                "cumulative_stats_by_url": all_stats[1],  # Table data
                "referrers": all_stats[2],
                "keywords": all_stats[3],
                "quizz": quizz_stats,
            }
        )
        return context
