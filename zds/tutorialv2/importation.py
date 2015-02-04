import datetime

from django.contrib.auth.decorators import login_required

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import FormView
from slugify import slugify
from zds.gallery.models import Gallery, UserGallery
from zds.member.decorator import can_write_and_read_now
from zds.tutorialv2.forms import ImportMarkdownForm
from zds.tutorialv2.models import PublishableContent, init_new_repo
from django.utils.translation import ugettext as _

from os.path import isdir, join
from os import makedirs
import zipfile

try:
    import ujson as json_reader
except ImportError:
    try:
        import simplejson as json_reader
    except ImportError:
        import json as json_reader


class BadArchiveError(Exception):
    """ The exception that is raised when a bad archive is sent """
    message = u''

    def __init__(self, reason):
        self.message = reason


def import_manifest_from_markdown_zip(request, publishable_content):
    """
    import a markdown archive, checks its good format
    :return a tuple with parsed man data and valid archive file
    :raise BadArchiveError if the archive is not well formed
    """

    archive = request.FILES["file"]
    ext = str(archive).split(".")[-1]
    if ext == "zip":
        zfile = zipfile.ZipFile(archive, "a")
        for i in zfile.namelist():
            ph = i
            if ph == "manifest.json":
                json_data = zfile.read(i)
                mandata = json_reader.loads(json_data)
                ck_zip = zipfile.ZipFile(archive, "r")
                (check, reason) = check_json(mandata, publishable_content, ck_zip)
                if not check:
                    raise BadArchiveError(reason)
                return mandata
    else:
        raise BadArchiveError(_(u'L\'archive doit être un fichier zip bien formé.'))


def check_json(data, content, zip_file):
    """
    check that the archive is coherent
    :return a tuple with a boolean accepting the mandata and archive and the reason we refuse it if so, None otherwise.
    """
    if "title" not in data:
        return (False, _(u"Le tutoriel que vous souhaitez importer manque de titre"))
    if "type" not in data:
        return (False, _(u"Les métadonnées du tutoriel à importer ne nous permettent pas de connaître son type"))
    if "children" not in data or isinstance(data['children'], type([])):
        return (False, _(u"Les métadonnées ne permettent pas de trouver la hiérarchie du contenu."))
    if "version" not in data or int(data["version"]) < 2:
        return (False, _(u"La version des méta données est trop ancienne."))
    if content.is_article() and data["type"] == "TUTORIAL":
        return (False, _(u"Vous essayez d'importer un tutoriel dans un article"))
    if content.is_tutorial() and data["type"] == "ARTICLE":
        return (False, _(u"Vous essayez d'importer un article dans un tutoriel"))
    for child in iterate_children(data):
        full_name = zip_file.filename[:-4] + child
        if full_name not in zip_file.namelist():
            return (False, _(u"Vos métadonnées ne sont pas cohérentes avec les autres données envoyées"))
    return (True, None)


def iterate_children(man_data, parent="", level=0):
    """
    :return an iterator over all the children's name for all the submited content
    """
    for element in man_data["children"]:
        if element["object"] == "extract" and level <= 2:
            yield parent + "/" + element["slug"]
        elif element["objet"] == "container" and level < 2:
            for e in iterate_children(element, parent + "/" + element["slug"], level + 1):
                yield e


class ImportMarkdownView(FormView):
    """
    Will handle importation from a markdown archive
    """

    model = PublishableContent
    form_class = ImportMarkdownForm

    @method_decorator(login_required)
    @method_decorator(can_write_and_read_now)
    def dispatch(self, *args, **kwargs):
        """rewrite this method to ensure decoration"""
        return super(ImportMarkdownView, self).dispatch(*args, **kwargs)

    def get_object(self, queryset=None):

        if 'pk' not in self.kwargs:
            return None
        return get_object_or_404(PublishableContent, pk=self.kwargs['pk'])

    def form_valid(self, form):
        context = self.get_context_data()
        content = context["content"]
        is_new = content is None
        if is_new:

            content = PublishableContent()
        else:
            versioned = context["content"].load_version()

        try:
            man, zip_file = import_manifest_from_markdown_zip(self.request, content)
            # create the object:
            content.title = man['title']
            content.description = man["description"]
            if is_new:
                content.type = form.cleaned_data["type"]
                content.creation_date = datetime.now()
                gal = Gallery()
                gal.title = man["title"]
                gal.slug = slugify(man["title"])
                gal.pubdate = datetime.now()
                gal.save()
                # Attach user to gallery
                userg = UserGallery()
                userg.gallery = gal
                userg.mode = "W"  # write mode
                userg.user = self.request.user
                userg.save()
                content.gallery = gal

            content.licence = form.cleaned_data["licence"]
            content.save()
            if is_new:
                # second if is_new because we had to save before init a new git repository
                init_new_repo(content, man['introduction'], man['conclusion'], "importation")
                versioned = content.load_version()

        except (BadArchiveError, KeyError):
            # set error on form
            pass

        # now we have to send all the archive content into the repository
        repo = versioned.repository
        for file in zip_file.filename():
            # if we have new directory
            if file.endswith("/") and not isdir(join(versioned.get_path(), file)):
                makedirs(file)
            # uf we have a file
            elif not file.endswith("/"):
                with open(join(versioned.get_path(), file), "w") as content_file:
                    content_file.write(zip_file.read(file))
            repo.index.add([join(versioned.get_path(), file)])
        # Todo: use commit message from form
        commit = repo.index.commit("Importation")
        content.sha_draft = commit.hexsha
        content.save()
