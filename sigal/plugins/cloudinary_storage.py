import datetime
import functools
import logging
import os
import cloudinary
from sigal import gallery, signals
from sigal import settings as sigal_settings

logger = logging.getLogger(__name__)


class CloudinaryImage:
    type = "image"

    def __init__(self, public_id, settings):
        # Don't send signals.media_initialized, as this object has a different
        #  interfaceobject
        self._public_id = public_id
        self.name = public_id
        self.settings = settings
        self._resource = cloudinary.api.resource(public_id, image_metadata=True)
        self.filename = cloudinary.CloudinaryImage(self._public_id).build_url()
        # This exists, so we won't try to do anything in process_dir
        self.dst_path = "/dev/null"
        # needed by process_dir
        self.path = ""
        self.src_path = "src_path"

    @property
    def big(self):
        return self._resource.secure_url

    @property
    def thumbnail(self):
        # XXX use thumbnail size from settings
        return cloudinary.CloudinaryImage(self._public_id).build_url(
            transformation=[
                {'width': 220, 'height': 140},
            ]
        )

    @property
    def date(self):
        #XXX fixme
        return datetime.datetime.now()

    @property
    def exif(self):
        # XXX fixme
        return {}

    @property
    def raw_exif(self):
        # XXX fixme
        return {}


class CloudinaryAlbum(gallery.Album):

    def populate_from_resources(self, resources, settings):
        for r in resources:
            if r["resource_type"] == "image":
                media = CloudinaryImage(r["public_id"], settings)
            elif r["resource_type"] == "video":
                logger.warning("Can't do cloudinary videos yet")
                continue
            else:
                logger.warning("Unknown type %s for resource %s",
                               r["resource_type"], r["secure_url"])
                continue

            self.medias_count[media.type] += 1
            self.medias.append(media)

    @property
    def thumbnail(self):
        # Test the thumbnail from the Markdown file
        thumbnail = self.meta.get('thumbnail', [''])[0]
        thumbnail_medias = [m for m in self.medias if m.name == thumbnail]
        if thumbnail:
            if thumbnail_medias:
                return thumbnail_medias[0].thumbnail
            else:
                self.logger.warning("can't find thumb image mentioned in markdown")
        else:
            self.logger.warning("no thumbnail specified in markdown")


    #@property
    #def zip(self):
    #    # may not be implementable
    #    # perhaps make cloudinary and zip_gallery incompatible
    #    pass


#@functools.lru_cache()
def cloudinary_config(settings):
    cloud_name = settings["cloudinary_cloud_name"]
    api_key = settings["cloudinary_api_key"]
    api_secret = settings["cloudinary_api_secret"]
    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret
    )

def ai_callback(album, settings=None):
    is_cloudinary_album = os.path.exists(
        os.path.join(album.src_path, ".cloudinary")
    )
    if is_cloudinary_album:
        logger.info("%s is a cloudinary album", album.title)
        cloudinary_config(album.settings)
        album_tag = "sigal:{0}".format(album.name)
        resources = cloudinary.api.resources_by_tag(album_tag)["resources"]
        if not resources:
            logger.warning("No cloudinary images for album %s "
                           "(no images with tag %s)", album.name, album_tag)
            return

        album.__class__ = CloudinaryAlbum
        album.populate_from_resources(resources, settings)
        #import pdb; pdb.set_trace()


def register(settings):
    signals.album_initialized.connect(ai_callback)
    old_process_image = gallery.process_image
    # *args **kwargs 
    def process_image(filepath, outpath, settings):
        # XXX if non cloudinary album, use the old one
        #return old_process_image(filepath, outpath, settings)
        return sigal_settings.Status.SUCCESS

    gallery.process_image = process_image
