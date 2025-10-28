from simple_history.admin import SimpleHistoryAdmin

from django.contrib import admin
from system.models import *
from system.forms import MethodAdminForm
from crbrm import config
from ..models.tenant_settings import TenantSettings

from django.utils.safestring import mark_safe
from openpyxl import Workbook
from django.apps import apps
from django.http import HttpResponse
from users.forms import UserManageLayoutForm, TabForm
from utils.state_manager.mixin import StateManagerMixin
from import_export.admin import ImportExportModelAdmin
from .export_resources import (
    AccessRightResource,
    AttributeResource,
    ChartResource,
    CollectionResource,
    CommandResource,
    CommandGroupResource,
    DimensionResource,
    FormResource,
    FilterResource,
    HookResource,
    LifecycleResource,
    MenuResource,
    MethodResource,
    ObjectResource,
    RelationResource,
    RelationshipResource,
    SequenceResource,
    StateResource,
    TabFavoriteResource,
    TabResource,
    TableResource,
    TypeResource,
    ViewResource,
    WorkspaceResource,
    Notification,
    WidgetResource,
    UserManageLayoutResource,
    PqlResource
)
from utils.state_manager.admin_site import state_manager_admin_site

from system.documents.attribute_document_multi_tenant import (
    delete_attribute_document,
)

__all__ = [
    "AttributeAdmin",
    "DimensionAdmin",
    "LifeCycleAdmin",
    "RelationshipAdmin",
    "RelationAdmin",
    "SequenceAdmin",
    "FilterAdmin",
    "ChartAdmin",
    "SequenceNumeratorAdmin",
    "StateAdmin",
    "TypeAdmin",
    "MethodAdmin",
    "HookAdmin",
    "AccessRightAdmin",
    "CommandAdmin",
    "MenuAdmin",
    "TabFavoriteAdmin",
    "TabAdmin",
    "WorkspaceAdmin",
    "FormAdmin",
    "ViewAdmin",
    "ObjectAdmin",
    "TableAdmin",
    "FileAdmin",
    "SearchHistoryAdmin",
    "WidgetAdmin",
    "UserManageLayoutAdmin",
]

from django_tenants.utils import get_public_schema_name


class PrivateTenantOnlyMixin:
    """Allow Access to Private Tenant Only."""

    def _only_private_tenant_access(self, request):
        return True if request.tenant.schema_name != get_public_schema_name() else False

    def has_view_permission(self, request, view=None):
        return self._only_private_tenant_access(request)

    def has_add_permission(self, request, view=None):
        return self._only_private_tenant_access(request)

    def has_change_permission(self, request, view=None):
        return self._only_private_tenant_access(request)

    def has_delete_permission(self, request, view=None):
        return self._only_private_tenant_access(request)

    def has_view_or_change_permission(self, request, view=None):
        return self._only_private_tenant_access(request)


class AccessRightAdmin( PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin ):
    list_display = ("id", "label")
    resource_class = AccessRightResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class AttributeAdmin( PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin ):
    list_display = ("id", "label", "selection_list", "is_indexed")
    resource_class = AttributeResource
    search_fields = ["id", "name", "label"]
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    model_name = "attribute"

    def delete_model(self, request, obj):
        """
        Deletes the model instance and the corresponding AttributeDocument from Elasticsearch.

        Args:
            request: The current request.
            obj: The model instance being deleted.
        """
        host = request.get_host().lower()

        tenant = host.split(".")[0]

        super().delete_model(request, obj)

        delete_attribute_document(obj, f"{tenant}_{self.model_name}")

    def delete_queryset(self, request, queryset):
        """
        Deletes the queryset of model instances and their corresponding AttributeDocument from Elasticsearch.

        Args:
            request: The current request.
            queryset: The queryset of model instances being deleted.
        """
        host = request.get_host().lower()

        tenant = host.split(".")[0]
        for obj in queryset:
            delete_attribute_document(obj, f"{tenant}_{self.model_name}")

        super().delete_queryset(request, queryset)


class CollectionAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin ):
    list_display = ("id", "label", "creator")
    search_fields = ["id", "name", "label"]
    resource_class = CollectionResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if change:  # Check if this is an update
            old_obj = Collection.objects.get(pk=obj.pk)
            if old_obj.label != obj.label:  # Check if the label field is updated
                if (Collection.objects.filter(label=obj.label, creator=obj.creator).exists()
                    or Collection.recycle.filter(label=obj.label, creator=obj.creator).exists()):
                    raise ValidationError(f"Collection with this label: {obj.label} already exists.")
                
            return super().save_model(request, obj, form, change)
        else:  # This is a new instance
            if (Collection.objects.filter(label=obj.label, creator=obj.creator).exists()
                or Collection.recycle.filter(label=obj.label, creator=obj.creator).exists()):
                raise ValidationError(f"Collection with this label: {obj.label} already exists.")
            
            return super().save_model(request, obj, form, change)
    

class CommandAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    resource_class = CommandResource
    search_fields = ["id", "name", "label"]
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

class CommandGroupAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = CommandGroupResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

class DimensionAdmin( PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin ):
    list_display = ("id", "label")
    resource_class = DimensionResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class FilterAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "name", "label", "creator", "is_public")
    search_fields = ["id", "name", "label"]
    resource_class = FilterResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class ChartAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = ChartResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class FormAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = FormResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class HookAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label", "hook_type", "hook_action")
    search_fields = ["id", "name", "label"]
    resource_class = HookResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class LifeCycleAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = LifecycleResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    model_name = "lifecycle"


class MenuAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label", "context_type", "type", "is_default")
    search_fields = ["id", "name", "label", "context_type"]
    resource_class = MenuResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class MethodAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = (
        "id",
        "label",
        "name",
        "is_dynamic",
    )
    resource_class = MethodResource
    history_list_display = ("ip_address",)
    # change_form_template = 'admin/custom_change_form.html'
    save_on_top = True
    form = MethodAdminForm
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    autocomplete_fields = ("used_methods",)
    search_fields = ("name", "label")
    fieldsets = (
        ("Code Block", {"fields": ("body", "used_methods")}),
        (
            "Method Form",
            {"fields": ("name", "label", "description", "version", "creator")},
        ),
        (
            "Controller",
            {
                "fields": (
                    "is_hidden",
                    "is_deleted",
                    "is_protected",
                    "is_active",
                    "is_dynamic",
                    "is_hook",
                    "is_timeseries",
                    "migrationpush",
                    "properties",
                    "context_type",
                )
            },
        ),
        ("Times", {"fields": ("created_at", "updated_at", "deleted_at")}),
    )


class ObjectAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin, StateManagerMixin):

    list_display = (
        "db_id",
        "name",
        "type",
        "from_relation_count",
        "to_relation_count",
        "object_id",
    )
    resource_class = ObjectResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    search_fields = ["name", "object_id"]

    model_name = "object"

    def _get_manager_and_tenant(self, request):
        from utils.state_manager.request_context import get_state_manager
        from rest_framework.response import Response
        from rest_framework import status

        manager = get_state_manager()
        if not manager:
            return Response(
                {"error": "State manager not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        host = request.get_host().lower()
        tenant = host.split(".")[0]
        return manager, tenant
    
    def save_model(self, request, obj, form, change):
        """
        Saves the model instance and updates the corresponding ObjectDocument in Elasticsearch.

        Args:
            request: The current request.
            obj: The model instance being saved.
            form: The form used for saving the instance.
            change (bool): Indicates if the instance is being updated.
        """
        result = self._get_manager_and_tenant(request)
        if not isinstance(result, tuple):  # means it's a Response
            return result

        manager, tenant = result
        # if change:
        manager.index(objects=[obj])

        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """
        Deletes the model instance and the corresponding ObjectDocument from Elasticsearch.

        Args:
            request: The current request.
            obj: The model instance being deleted.
        """
        result = self._get_manager_and_tenant(request)
        if not isinstance(result, tuple):
            return result

        manager, tenant = result
        manager.index_delete(object_db_ids=[obj.db_id])

        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """
        Deletes the queryset of model instances and their corresponding ObjectDocuments from Elasticsearch.

        Args:
            request: The current request.
            queryset: The queryset of model instances being deleted.
        """
        result = self._get_manager_and_tenant(request)
        if not isinstance(result, tuple):
            return result

        manager, tenant = result
        manager.index_delete(object_db_ids=list(object.db_id for object in queryset))

        super().delete_queryset(request, queryset)

class RelationAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin,StateManagerMixin):
    list_display = ("id", "name", "relationship", "quantity", "from_id", "to_id")
    resource_class = RelationResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    search_fields = ["label", "from_id", "to_id", "name"]

    model_name = "relation"

    def _get_manager_and_tenant(self, request):
        """Return (manager, tenant) or None if manager is missing."""
        from utils.state_manager.request_context import get_state_manager
        from rest_framework.response import Response
        from rest_framework import status

        manager = get_state_manager()
        if not manager:
            return Response(
                {"error": "State manager not found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        host = request.get_host().lower()
        tenant = host.split(".")[0]
        return manager, tenant

    def save_model(self, request, obj, form, change):
        """
        Saves the model instance and updates the corresponding RelationDocument in Elasticsearch.

        Args:
            request: The current request.
            obj: The model instance being saved.
            form: The form used for saving the instance.
            change (bool): Indicates if the instance is being updated.
        """
        result = self._get_manager_and_tenant(request)
        if not isinstance(result, tuple):  # means it's a Response
            return result

        manager, tenant = result

        manager.index(relations=[obj])
        super().save_model(request, obj, form, change)

    def delete_model(self, request, obj):
        """
        Deletes the model instance and the corresponding RelationDocument from Elasticsearch.

        Args:
            request: The current request.
            obj: The model instance being deleted.
        """
        result = self._get_manager_and_tenant(request)
        if not isinstance(result, tuple):
            return result

        manager, tenant = result
        manager.index_delete(relation_ids=[obj.id])
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """
        Deletes the queryset of model instances and their corresponding RelationDocument from Elasticsearch.

        Args:
            request: The current request.
            queryset: The queryset of model instances being deleted.
        """
        result = self._get_manager_and_tenant(request)
        if not isinstance(result, tuple):
            return result

        manager, tenant = result
        manager.index_delete(relation_ids=[obj.id for obj in queryset])
        # for obj in queryset:
        #     manager.index_delete(relation_ids=[obj])

        super().delete_queryset(request, queryset)


class RelationshipAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label", "is_structured")
    search_fields = ["id", "name", "label"]
    resource_class = RelationshipResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class SequenceAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    resource_class = SequenceResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class SequenceNumeratorAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "type_id")
    history_list_display = ("ip_address",)

class StateAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = StateResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    model_name = "state"

class TabFavoriteAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    resource_class = TabFavoriteResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

class TabAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    resource_class = TabResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")
    form = TabForm

class TableAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = TableResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class TypeAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = TypeResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class ViewAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    resource_class = ViewResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class WorkspaceAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    resource_class = WorkspaceResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class FileAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label", "file")
    history_list_display = ("ip_address",)
    readonly_fields = ("file_code","created_at", "updated_at", "last_accessed_at")

    search_fields = ["id", "name", "label", "file_code"]

    def file(self, object):
        return mark_safe(f'<a href="{object.url}" target="_blank">{object.original_filename}</a>')

class DashboardAdmin(PrivateTenantOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "label", "creator")
    readonly_fields = ("created_at", "updated_at")


class FilterMenuAdmin(PrivateTenantOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "label")
    readonly_fields = ("created_at", "updated_at")


class LicenseAdmin(PrivateTenantOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "label")
    readonly_fields = ("created_at", "updated_at")


class SubscribedUserAdmin(PrivateTenantOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "object_id")


class SearchHistoryAdmin(PrivateTenantOnlyMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "creator",
        "searched_content",
    )
    search_fields = ["id", "searched_content"]


class NotificationAdmin(PrivateTenantOnlyMixin, admin.ModelAdmin):
    list_display = ("id", "name", "notification_type")
    search_fields = ["id", "name", "object_id"]
    readonly_fields = ("created_at", "updated_at")


class NotificationTemplateAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, admin.ModelAdmin):
    list_display = (
        "id",
        "get_access_type_display",
        "notification_sendtype",
        "notification_type",
        "nt_key_details",
    )

    def get_access_type_display(self, obj):
        data = dict(AccessRight.AccessType.choices)
        return data[int(obj.access_type)]

    readonly_fields = ("nt_key",)


class IconAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ("id", "name", "icon_type", "status")
    readonly_fields = ("created_at", "updated_at")


class HistoryAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ("object_id", "user", "event", "model", "created_at")
    search_fields = ["id", "event", "object_id"]
    readonly_fields = ("created_at",)


class CardAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    search_fields = ["id", "name", "label"]
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")


class TenantSettingsAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "category", "name", "label", "active")
    search_fields = ["id", "name", "label"]
    readonly_fields = ("created_at", "updated_at")

    # Define the export action
    def export_all_models(self, request, queryset):
        # Initialize a new workbook
        workbook = Workbook()

        # Rename the default active sheet
        active_sheet = workbook.active
        active_sheet.title = "Summary"

        # List of models to export
        models_to_export = [
        'Attribute', 'Dimension', 'Lifecycle', 'Relationship', 'Sequence',
        'SequenceNumerator', 'State', 'Type', 'Method', 'Hook', 'AccessRight',
        'Command', 'CommandGroup', 'Menu', 'Filter', 'FilterMenu', 'Dashboard',
        'Chart', 'TabFavorite','Tab', 'Workspace', 'Form', 'View', 'table', 'File',
        'Collection', 'License', 'SubscribedUser', 'SearchHistory',
        'NotificationTemplate', 'Icon', 'Card', 'TenantSettings',
        ]

        try:
            # Iterate over each model and add data to a new sheet
            for model_name in models_to_export:
                try:
                    model = apps.get_model(app_label='system', model_name=model_name)
                    sheet = workbook.create_sheet(title=model_name)

                    # Write header row
                    fields = [field.name for field in model._meta.fields]
                    sheet.append(fields)

                    # Write data rows
                    for obj in model.objects.all():
                        row = []
                        for field in fields:
                            value = getattr(obj, field)

                            # Convert non-primitive types to strings
                            if isinstance(value, (int, float, str, bool, None.__class__)):
                                row.append(value)
                            else:
                                row.append(str(value))
                        sheet.append(row)
                except LookupError:
                    print(f"Model {model_name} not found.")

            # Remove the default empty sheet if unused
            if "Summary" in workbook.sheetnames:
                workbook.remove(workbook["Summary"])

            # Prepare the response
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = 'attachment; filename="models_data.xlsx"'

            # Save the workbook to the response
            workbook.save(response)
            return response

        except Exception as e:
            print(f"An error occurred: {e}")
            raise

    # Ignore queryset and make the action work without selected items
    export_all_models.short_description = "Export all models data as an Excel file with multiple sheets"
    actions = ["export_all_models"]

    def has_module_permission(self, request):
        return True  # Allow module-level access


class CollectionObjectAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id","display", "collection", "collection_object", "is_cut")

    def display(self, obj):
        return str(obj)


class CollaborationAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, admin.ModelAdmin):
    search_fields = ["id", "object_id"]
    list_display = ("id", "object_id", "created_at")

class WidgetAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "label")
    resource_class = WidgetResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": (
                "name", 
                "label", 
                "creator",
                "modifier",
                "description",
                "is_deleted",
                "deleted_at",
                "is_protected",
                "is_public",
                "migrationpush",
                "properties",
                "created_at",
                "updated_at",
            ),
        }),
    )

class UserManageLayoutAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "name")
    resource_class = UserManageLayoutResource
    history_list_display = ("ip_address",)
    readonly_fields = ("created_at", "updated_at")
    form = UserManageLayoutForm


class PqlAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = ("id", "name", "label", "creator", "is_public")
    search_fields = ["id", "name", "label"]
    resource_class = PqlResource
    readonly_fields = ("created_at", "updated_at")


class TimeSeriesAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = (
        "id",
        "label",
        "name",
        "is_active",
    )
    readonly_fields = ("created_at", "updated_at", "deleted_at", "last_run_at", "data")
    search_fields = ("name", "label")


class ApiSchedulerAdmin(PrivateTenantOnlyMixin, ImportExportModelAdmin, SimpleHistoryAdmin):
    list_display = (
        "id",
        "schedule_type",
        "api_url",
        "is_active",
        "is_completed"
    )
    readonly_fields = ("created_at", "updated_at", "deleted_at" , "last_run_at")
    search_fields = ("api_url", "label")



state_manager_admin_site.register(TenantSettings, TenantSettingsAdmin)

state_manager_admin_site.register(Attribute, AttributeAdmin)
state_manager_admin_site.register(Dimension, DimensionAdmin)
state_manager_admin_site.register(Lifecycle, LifeCycleAdmin)
state_manager_admin_site.register(Relationship, RelationshipAdmin)
state_manager_admin_site.register(Relation, RelationAdmin)
state_manager_admin_site.register(Sequence, SequenceAdmin)
state_manager_admin_site.register(SequenceNumerator, SequenceNumeratorAdmin)
state_manager_admin_site.register(State, StateAdmin)
state_manager_admin_site.register(Type, TypeAdmin)
state_manager_admin_site.register(Object, ObjectAdmin)
state_manager_admin_site.register(Method, MethodAdmin)
state_manager_admin_site.register(Hook, HookAdmin)
state_manager_admin_site.register(AccessRight, AccessRightAdmin)
state_manager_admin_site.register(Command, CommandAdmin)
state_manager_admin_site.register(CommandGroup, CommandGroupAdmin)
state_manager_admin_site.register(Menu, MenuAdmin)
state_manager_admin_site.register(Filter, FilterAdmin)
state_manager_admin_site.register(FilterMenu, FilterMenuAdmin)
state_manager_admin_site.register(Dashboard, DashboardAdmin)
state_manager_admin_site.register(Chart, ChartAdmin)
state_manager_admin_site.register(TabFavorite, TabFavoriteAdmin)
state_manager_admin_site.register(Tab, TabAdmin)
state_manager_admin_site.register(Workspace, WorkspaceAdmin)
state_manager_admin_site.register(Form, FormAdmin)
state_manager_admin_site.register(View, ViewAdmin)
state_manager_admin_site.register(Table, TableAdmin)
state_manager_admin_site.register(File, FileAdmin)
state_manager_admin_site.register(Collection, CollectionAdmin)
state_manager_admin_site.register(License, LicenseAdmin)
state_manager_admin_site.register(SubscribedUser, SubscribedUserAdmin)
state_manager_admin_site.register(SearchHistory, SearchHistoryAdmin)
state_manager_admin_site.register(Notification, NotificationAdmin)
state_manager_admin_site.register(NotificationTemplate, NotificationTemplateAdmin)
state_manager_admin_site.register(Icon, IconAdmin)
state_manager_admin_site.register(History, HistoryAdmin)
state_manager_admin_site.register(Card, CardAdmin)
state_manager_admin_site.register(CollectionObject, CollectionObjectAdmin)
state_manager_admin_site.register(Collaboration, CollaborationAdmin)
state_manager_admin_site.register(Widget, WidgetAdmin)
state_manager_admin_site.register(UserManageLayout, UserManageLayoutAdmin)
state_manager_admin_site.register(Pql, PqlAdmin)
state_manager_admin_site.register(TimeSeries, TimeSeriesAdmin)
state_manager_admin_site.register(ApiScheduler, ApiSchedulerAdmin)

