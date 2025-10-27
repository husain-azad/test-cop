from rest_framework import viewsets, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response

from django.db.models import Case, When
from django.core.cache import cache

from utils.state_manager.mixin import StateManagerMixin
from system.api.serializers.chart import ChartSerializer
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from users.authentication import CustomTokenAuthentication
from copy import deepcopy
from system.api.helper import get_custom_activity_logger, generic_old_and_new_update_values
from system.api.views.decorators import user_access_check
from django.core.exceptions import PermissionDenied
from crbrm.config import REDIS_TIMEOUT


__all__ = ["ChartViewSet", "ChartNameView", "ChartListView"]


class ChartViewSet(StateManagerMixin, viewsets.ModelViewSet):
    """
    ChartViewSet is default view for :class:`.Chart`. This view operates List, Get, Update and Delete functions.

    **Example Request:**

    .. code-block:: python

        GET -> /api/system/chart/
            data: None

        POST -> /api/system/chart/

        PUT -> /api/system/chart/1/

        PATCH -> /api/system/chart/1/

        DELETE -> /api/system/chart/1/

        Documentation : api_doc_strings/crbrm/system/api/views/chart.md #Chart-ViewSet
    """

    queryset = Chart.objects.select_related("creator").all()
    serializer_class = ChartSerializer
    authentication_classes = [CustomTokenAuthentication]
    
    # def list(self, request, *args, **kwargs):
    #     check = user_access_check(user=request.user, required_permissions=["READ"])
    #     if not isinstance(check, bool):
    #         return Response(check, status=status.HTTP_400_BAD_REQUEST)
    #
    #     cache_key = f"{self.request.tenant}_chart_model_redis"
    #
    #     queryset = (
    #         Chart.objects.select_related("creator").all().order_by("-created_at")
    #     )
    #
    #     obj_ids = [i.id for i in queryset]
    #     page = self.paginate_queryset(queryset)
    #     if page is not None:
    #         # cache.delete(cache_key)
    #         if cache_key in cache:
    #             check_cache_keys = RedisModel.check_keys(
    #                 cache_key=cache_key, keys=obj_ids
    #             )
    #             cache_data_get = RedisModel.filter(cache_key=cache_key, keys=obj_ids)
    #
    #             if len(check_cache_keys) == 0 and cache_data_get:
    #                 return self.get_paginated_response(cache_data_get.values())
    #
    #         serializer = self.get_serializer(page, many=True)
    #         response = Response(serializer.data)
    #
    #         if serializer.data:
    #             for tdata in serializer.data:
    #                 RedisModel.create(cache_key=cache_key, key=tdata["id"], value=tdata)
    #
    #         return self.get_paginated_response(response.data)
    #
    #     serializer = self.get_serializer(queryset, many=True)
    #     return Response(serializer.data)

# new code for 12 nov
    def list(self, request, *args, **kwargs):
        # User access check
        check = user_access_check(user=request.user, required_permissions=["READ"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"{self.request.tenant}_chart_model_redis"
        queryset = Chart.objects.select_related("creator").all().order_by("-created_at")
        obj_ids = [chart.id for chart in queryset]

        results = []
        fetched_cache = cache.get(cache_key) if cache_key in cache else None

        # Check for paginated response if necessary
        page = self.paginate_queryset(queryset)

        # Iterate through obj_ids and retrieve from cache or DB as needed
        for chart_id in obj_ids:
                if fetched_cache and chart_id in fetched_cache:
                    results.append(fetched_cache[chart_id])
                else:
                    chart_object = Chart.objects.get(id=chart_id)
                    serializer = ChartSerializer(chart_object)
                    serializer_data = serializer.data
                    results.append(serializer_data)

                    # Update cache with newly fetched data
                    if fetched_cache is None:
                        new_record = {chart_id: serializer_data}
                        cache.set(cache_key, new_record, timeout=REDIS_TIMEOUT)
                        fetched_cache = new_record
                    else:
                        fetched_cache[chart_id] = serializer_data
                        cache.set(cache_key, fetched_cache, timeout=REDIS_TIMEOUT)

        if page is not None:
            # Paginate results
            paginated_results = self.get_paginated_response(results)
            return paginated_results

        # If not paginated, retrieve data from cache or serialize directly

        data_dict = {
            "count": len(results),
            "results": results,
        }

        return Response(data_dict)


    def perform_create(self, serializer):
        check = user_access_check(user=self.request.user, required_permissions=["READ", "CREATE"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            transaction_point = transaction.savepoint()
            try:
                serializer.save(creator=self.request.user)
                chart_obj = Chart.objects.get(id=serializer.data["id"])
                get_custom_activity_logger("CREATE", chart_obj, self.request.user, "", model="chart")
                transaction.savepoint_commit(transaction_point)
            except Exception as error:
                transaction.savepoint_rollback(transaction_point)
                return Response({"error": _(str(error))}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        check = user_access_check(user=self.request.user, required_permissions=["READ", "MODIFY"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            transaction_point = transaction.savepoint()
            try:
                instance = self.get_object()
                serializer = self.get_serializer(instance, data=request.data, partial=True)
                serializer.is_valid(raise_exception=True)

                old_instance = deepcopy(instance)
                serializer.save(modifier=self.request.user)
                details = serializer.data

                generic_old_and_new_update_values(
                    request, request.data, old_instance, "chart", "MODIFY"
                )
                transaction.savepoint_commit(transaction_point)
                return Response(details)
            except Exception as error:
                transaction.savepoint_rollback(transaction_point)
                return Response({"error": _(str(error))}, status=status.HTTP_400_BAD_REQUEST)

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            # queryset just for schema generation metadata
            return Chart.objects.none()

        return super().get_queryset().filter(creator=self.request.user)
    
    def perform_destroy(self, instance):
        check = user_access_check(user=self.request.user, required_permissions=["READ", "DELETE"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)
        
        get_custom_activity_logger("DELETE", instance, self.request.user, model="chart")

        return super().perform_destroy(instance)


class ChartNameView(StateManagerMixin, APIView):
    """
    ChartNameView is view for query :class:`.Chart` type with name. With this endpoint we can query related object model with name attribute.

    **Example Request:**

    .. code-block:: python

        GET -> /api/system/chart/name/{chart_name}/
            data: None

    Documentation : api_doc_strings/crbrm/system/api/views/chart.md Chart-Name-View
    """

    authentication_classes = [CustomTokenAuthentication]
    
    def get(self, request, chart_name):
        check = user_access_check(user=request.user, required_permissions=["READ"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)
        
        chart_obj = ChartSerializer(
            Chart.objects.get(name=Chart, creator=self.request.user)
        )
        return Response(data=chart_obj.data)


class ChartListView(StateManagerMixin, generics.ListAPIView):
    """
    ChartListView returns objects, which requested with parameters.

    * API supports multiple ids
    * If more than one id is given, the ids must be separated by commas.

    **Example Request:**

    .. code-block:: python

        GET -> /api/system/charts/list/?ids=1
            data: None

    **Example Response:**

    .. code-block:: python

        {
            "count": 1,
            "next": null,
            "previous": null,
            "results": [
                {
                    "id": 1,
                    "creator": "PLM Manager",
                    "modifier": null,
                    "filter_detail": {
                        "id": 1,
                        "creator": 1,
                        "modifier": null,
                        "description": null,
                        "is_deleted": false,
                        "deleted_at": null,
                        "is_protected": false,
                        "name": "test",
                        "label": "test",
                        "fields": [
                            {
                                "name": "is_latest_revision",
                                "type": "system",
                                "value": true,
                                "operand": "contains"
                            }
                        ],
                        "is_public": false,
                        "is_hidden": false,
                        "properties": null,
                        "created_at": "2022-09-06T10:50:09.619932+00:00",
                        "updated_at": "2022-09-06T10:50:09.619987+00:00"
                    },
                    "created_at": "2022-09-06T13:50:09.691173+03:00",
                    "updated_at": "2022-09-06T13:50:09.691236+03:00",
                    "description": null,
                    "is_deleted": false,
                    "deleted_at": null,
                    "is_protected": false,
                    "name": "test",
                    "label": "test",
                    "chart_type": 3,
                    "is_hidden": false,
                    "fields": {
                        "type": 3,
                        "attribute": "state",
                        "date_type": "_week",
                        "aggregation": "avg"
                    },
                    "is_public": false,
                    "properties": null,
                    "filter": 1
                }
            ]
        }
    Documentation : api_doc_strings/crbrm/system/api/views/chart.md #Chart-List-View
    """

    serializer_class = ChartSerializer
    authentication_classes = [CustomTokenAuthentication]
    
    def get_queryset(self):
        check = user_access_check(user=self.request.user, required_permissions=["READ"])
        if not isinstance(check, bool):
            raise PermissionDenied(_(check["error"]))
        
        try:
            ids = self.request.query_params.get("ids", None)
            ids = [x for x in ids.split(",")]
            preserved = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(ids)])
            queryset = Chart.objects.filter(
                pk__in=ids, creator=self.request.user
            ).order_by(preserved)
        except:
            queryset = Chart.objects.none()

        return queryset


class ChartPublicView(StateManagerMixin, generics.ListAPIView):
    """
    Provides a list of charts that are marked as public.
    Checks user permissions before retrieving public charts.
    Returns serialized chart data.

    Args:
        self.request.user (User): Authenticated user making the request.

    Returns:
        QuerySet: Filtered queryset containing only public Chart objects.

    Documentation : api_doc_strings/crbrm/system/api/views/chart.md #Chart-Public-View
    """
    queryset = Chart.objects.all()
    serializer_class = ChartSerializer
    authentication_classes = [CustomTokenAuthentication]
    
    def get_queryset(self):
        check = user_access_check(user=self.request.user, required_permissions=["READ"])
        if not isinstance(check, bool):
            raise PermissionDenied(_(check["error"]))
        
        return super().get_queryset().filter(is_public=True)
