from django.db import models
from django.utils.translation import gettext_lazy as _
from django.template.defaultfilters import slugify
from django.db.models.signals import pre_save, post_save, post_delete
from django.db import connection
from django.core.cache import cache

from system.models import BaseModel
from system.models.dimension import Dimension


class Attribute(BaseModel):

    """
    :class:`.Attribute` model class.

    This model class is the smallest part of application. All models, classes, types can use this class.
    Mostly referanced with JSON Fields.

    .. attribute:: variable_type

        Defines data type of related :class:`.Attribute` instance. Application will display form elements and works regarding to this field.

        Type Choices:

        * String
        * Integer
        * Float
        * DateTime
        * Boolean
        * Json

    .. attribute:: default

        Defines, default value of :class:`.Attribute`. When referanced this attibute instance, default value will be shown on the system (both UI and Backend).

    .. attribute:: icon

        Defines icon of defined :class:`.Attribute` instance.

    .. attribute:: multi_value

        Defines if attribute can store more than one value in an array. This field is related with `choice` field. If field sets as `True` then attribute store valuen in an array of values

        `(['value1', 'value2', 'value3'])`

        If field sets as `False` then attribute will store single value like


    .. attribute:: max_length

        Defines max length for :class:`.Attribute` value.

    .. attribute:: multi_line

        Defines if :class:`.Attribute` has more than one line or not. If this field sets to `True`, we can expect, UI will show `multi-line textbox` or `richtext editor`.

    .. attribute:: reset_on_clone

        If this field set to True, while :class:`.Attribute` instance cloning, the data will be reset.

    .. attribute:: reset_on_revision

        If this field set to True, while :class:`.Attribute` instance revision, the data will be reset.

    .. attribute:: is_unique

        Defines if :class:`.Attribute` is unique or not.

    .. attribute:: is_active

        Defines if :class:`.Attribute` is active or not.

    .. attribute:: is_indexed

        Defines if :class:`.Attribute` is indexed in database level or not.

    .. attribute:: is_encrypted

        Defines if :class:`.Attribute` is encrypted or not.

    .. attribute:: is_hidden

        Defines if :class:`.Attribute` is hidden or not.

    .. attribute:: is_system_column

        Defines if the :class:`.Attribute` is system column or not.
        If sets to `True`, related data will be stored in `Type` instance, otherwise will store on `attribute` field.

    .. attribute:: dimension

        Defines if :class:`.Attribute` has dimension relation or not.

    .. attribute:: css

        Default style settings for :class:`.Attribute`.

    .. attribute:: is_protected

        It must be set to `True` for :class:`.Attribute` created by the system, which may cause serious problems in the operation of the application if deleted.
        Thus, the application will not allow admin and users to delete these values.

    .. attribute:: allow_custom_value

        If the allow_custom_value flag is true, then we can add manual entry for the selection_list at the object level.

    .. attribute:: selection_list

        Defines selection list for :class:`.Attribute`. This field is related with `variable_type`.
        For using this field we need to choose `choice` from `variable_type`.
        After that we can know that, we will display these field items as choice source.

        Gender Sample:

        .. code-block:: json

            [
                {
                    "value": "female",
                    "name": "Female"
                },
                {
                    "value": "male",
                    "name": "Male"
                }
            ]

    .. attribute:: properties

        Defines properties for :class:`.Attribute`. Reserved for future use. Field is JSONField.

    """

    class VariableDataTypes(models.IntegerChoices):
        String = 1
        Integer = 2
        Float = 3
        Datetime = 4
        Boolean = 5
        Json = 6
        Vector = 7

    variable_type = models.IntegerField(
        verbose_name=_("variable type"),
        blank=False,
        null=False,
        choices=VariableDataTypes.choices,
        default=1,
    )

    vector_dimension = models.PositiveIntegerField(
        verbose_name=_("vector dimension"),
        default=1,
        null=False,
        blank=False,
    )

    default = models.CharField(
        verbose_name=_("default"),
        max_length=240,
        blank=True,
        null=True,
    )

    icon = models.CharField(
        verbose_name=_("icon"),
        max_length=240,
        blank=True,
        null=True,
    )

    multi_value = models.BooleanField(
        verbose_name=_("multi value"),
        default=False,
        null=False,
        blank=False,
    )

    max_length = models.PositiveIntegerField(
        verbose_name=_("max length"),
        default=0,
        null=False,
        blank=False,
    )

    multi_line = models.BooleanField(
        verbose_name=_("multi line"),
        default=False,
        null=False,
        blank=False,
    )

    reset_on_clone = models.BooleanField(
        verbose_name=_("reset on clone"),
        default=False,
        null=False,
        blank=False,
    )

    reset_on_revision = models.BooleanField(
        verbose_name=_("reset on revision"),
        default=False,
        null=False,
        blank=False,
    )

    is_unique = models.BooleanField(
        verbose_name=_("is unique"),
        default=False,
        null=False,
        blank=False,
    )

    is_system_column = models.BooleanField(
        verbose_name=_("is system column"),
        default=False,
        null=False,
        blank=False,
    )

    is_active = models.BooleanField(
        verbose_name=_("is active"),
        default=True,
        null=False,
        blank=False,
    )

    is_indexed = models.BooleanField(
        verbose_name=_("is indexed"),
        default=False,
        null=False,
        blank=False,
    )

    is_encrypted = models.BooleanField(
        verbose_name=_("is encrypted"),
        default=False,
        null=False,
        blank=False,
    )

    is_hidden = models.BooleanField(
        verbose_name=_("is hidden"),
        default=False,
        null=False,
        blank=False,
    )

    is_rollup = models.BooleanField(
        verbose_name=_("is rollup"),
        default=False,
        null=False,
        blank=False,
    )

    allow_custom_value = models.BooleanField(
        verbose_name=_("allow custom value"),
        default=False,
        null=False,
        blank=False,
    )

    migrationpush = models.BooleanField(
        verbose_name=_("migrationpush"),
        default=True
    )

    dimension = models.ForeignKey(
        Dimension,
        verbose_name=_("dimension"),
        on_delete=models.CASCADE,
        related_name="%(class)s_dimension",
        blank=True,
        null=True,
    )

    css = models.TextField(verbose_name=_("css"), blank=True, null=True)

    selection_list = models.JSONField(
        verbose_name=_("selection_list"), blank=True, null=True
    )

    properties = models.JSONField(verbose_name=_("properties"), blank=True, null=True)

    # history = get_custom_historical_record()

    # region: State Manager Foreign Field Fetchers

    @property
    def sm_dimension(self):
        id = self.dimension_id
        
        if id is None:
            return None
        
        if hasattr(self, "_cached_sm_dimension") and self._cached_sm_dimension.id == id:
            return self._cached_sm_dimension
        
        # from utils.state_manager.request_context import get_state_manager

        # instance = get_state_manager().get_dimension_by_id(id, disable_all_checks=True)

        # State Manager doesn't have Dimension support yet
        instance = self.dimension
        self._cached_sm_dimension = instance
        return instance
    
    # endregion: State Manager Foreign Field Fetchers

    class Meta:
        verbose_name = "attribute"
        verbose_name_plural = "attributes"

    def __str__(self):
        return self.label


def on_pre_save(sender, instance, *args, **kwargs):
    if not instance.name:
        instance.name = slugify(instance.label)


pre_save.connect(on_pre_save, Attribute)


def on_post_save(sender, instance, created, **kwargs):
    from system.api.serializers.attribute import AttributeSerializer
    from system.documents.redis_document import RedisModel

    tenant = connection.schema_name

    cache_key = f"{tenant}_attribute_model_redis"

    attributes_data_key = f"{tenant}_attributes_data"
    new_att_type_key = f"{tenant}_new_att_type"

    cache.delete(attributes_data_key)
    cache.delete(new_att_type_key)

    if created:
        new_data = AttributeSerializer(instance)
        RedisModel.create(cache_key=cache_key, key=instance.id, value=new_data.data)
    else:
        RedisModel.remove(cache_key=cache_key, key=instance.id)


post_save.connect(on_post_save, Attribute)


def on_post_delete(sender, instance, *args, **kwargs):
    from system.documents.redis_document import RedisModel
    from system.api.helper import get_custom_activity_logger

    tenant = connection.schema_name

    cache_key = f"{tenant}_attribute_model_redis"
    attributes_data_key = f"{tenant}_attributes_data"
    new_att_type_key = f"{tenant}_new_att_type"

    cache.delete(attributes_data_key)
    cache.delete(new_att_type_key)

    RedisModel.remove(cache_key=cache_key, key=instance.id)

    get_custom_activity_logger("DELETE", instance, instance.creator, model="attribute")


post_delete.connect(on_post_delete, Attribute)
