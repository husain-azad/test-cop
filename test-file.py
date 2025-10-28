from rest_framework import viewsets, status
from rest_framework.response import Response
from django.core.cache import cache
from rest_framework.views import APIView
from copy import deepcopy
from utils.state_manager.mixin import StateManagerMixin
from system.models import Card, Type
from system.api.serializers.card import CardSerializer, MaskCardSerializer
from users.authentication import CustomTokenAuthentication
from system.tasks.notification import test_send_notification_to_subscribers
from system.api.helper import get_custom_activity_logger, generic_old_and_new_update_values
from system.documents.redis_document import RedisModel
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from system.api.views.decorators import user_access_check
from crbrm.config import REDIS_TIMEOUT

__all__ = ["CardViewSet"]


class CardViewSet(StateManagerMixin, viewsets.ModelViewSet):
    """
    CardViewSet is default view for :class:`.Card`. This view operates List, Get, Update and Delete functions.

    **Example Request:**

    .. code-block:: python

        GET -> /api/system/card/
            data: None

        GET -> /api/system/card/?mask=basic
            -> If mask=basic then it returns the basic information(id, name, label).

        GET -> /api/system/card/?card_type=Workflow

        POST -> /api/system/card/

        PUT -> /api/system/card/1/

        PATCH -> /api/system/card/1/

        DELETE -> /api/system/card/1/

    Documentation : api_doc_strings/crbrm/system/api/views/card.md #Card-ViewSet
    """

    queryset = Card.objects.select_related("creator", "type").all().order_by("-created_at")
    serializer_class = CardSerializer
    authentication_classes = [CustomTokenAuthentication]

    # New card list code 12 Nov
    def list(self, request, *args, **kwargs):
        from utils.state_manager.request_context import get_state_manager
        manager = get_state_manager()
        if manager is None:
            return Response({"error": "State manager not found"}, status=status.HTTP_400_BAD_REQUEST)
        
        check = user_access_check(user=request.user, required_permissions=["READ"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"{self.request.tenant}_new_card_model_redis"
        type_id = request.GET.get("type_id", None)
        card_type = request.GET.get("card_type", None)
        is_mask = self.request.GET.get("mask", "detail")

        # if type_id == "null" and card_type:
        #     query = f"""SELECT * FROM "system_card" WHERE (NOT ("system_card"."is_deleted") AND "system_card"."card_type" = '{str(card_type)}' AND "system_card"."type_id" IS NULL) ORDER BY "system_card"."created_at" DESC;"""
        # elif type_id and card_type:
        #     query = f"""SELECT * FROM "system_card" WHERE (NOT ("system_card"."is_deleted") AND "system_card"."card_type" = '{str(card_type)}' AND "system_card"."type_id" = {int(type_id)}) ORDER BY "system_card"."created_at" DESC"""
        # elif type_id == "null":
        #     query = """SELECT * FROM "system_card" WHERE (NOT ("system_card"."is_deleted") AND "system_card"."type_id" IS NULL) ORDER BY "system_card"."created_at" DESC;"""
        # elif type_id:
        #     query = f"""SELECT * FROM "system_card" WHERE (NOT ("system_card"."is_deleted") AND "system_card"."type_id" = {int(type_id)}) ORDER BY "system_card"."created_at" DESC;"""
        # elif card_type:
        #     query = f"""SELECT * FROM "system_card" WHERE (NOT ("system_card"."is_deleted") AND "system_card"."card_type" = '{str(card_type)}') ORDER BY "system_card"."created_at" DESC;"""
        # else:
        #     query = """SELECT * FROM "system_card" WHERE NOT ("system_card"."is_deleted") ORDER BY "system_card"."created_at" DESC;"""

        # queryset = Card.objects.raw(query)

        filters = {"is_deleted": False}

        # Handle type_id
        if type_id == "null":
            filters["type_id__isnull"] = True
        elif type_id:
            filters["type_id"] = int(type_id)

        # Handle card_type
        if card_type:
            filters["card_type"] = card_type

        # Get queryset
        queryset = manager.filter_cards(**filters)


        # Final ordering
        queryset = sorted(queryset, key=lambda card: card.created_at, reverse=True)
    
        # fallback to parent if child has no cards
        if not queryset and type_id:
            try:
                # current_type = Type.objects.filter(id=int(type_id)).first()
                current_type = manager.get_type_by_id(int(type_id))
                if current_type and current_type.parent_id:
                    parent_type_id = current_type.parent_id
                    # query = query.replace(
                    #     f'"system_card"."type_id" = {int(type_id)}',
                    #     f'"system_card"."type_id" = {parent_type_id}'
                    # )
                    # queryset = list(Card.objects.raw(query))
                    # queryset = Card.objects.filter(type_id=parent_type_id)
                    queryset = manager.filter_cards(type_id =int(parent_type_id))
                    queryset = sorted(queryset, key=lambda card: card.created_at, reverse=True)

            except Exception as e:
                pass

        if is_mask.lower() == "basic":
            serializer = MaskCardSerializer(queryset, many=True)
            return Response(data={"count": len(queryset), "results": serializer.data})
        # fetched_cache = cache.get(cache_key) if cache_key in cache else None
        results = []
        obj_ids = [i.id for i in queryset]
        card_map = {card.id : card for card in queryset}

        # results = list(map(lambda card_id: fetched_cache.get(card_id) or card_map[card_id], obj_ids))

        def get_card_or_fetch(card_id):
            fetched_card = None
            if cache_key:
                fetched_card = RedisModel.get(cache_key=cache_key, key=card_id)

            if fetched_card != False:
                return fetched_card

            card_object = card_map.get(card_id)
            if card_object:
                serializer = CardSerializer(card_object)
                serializer_data = serializer.data
                RedisModel.create(cache_key=cache_key, key=card_object.id, value=serializer_data)
                return serializer_data

            return None
        results = list(filter(None, map(get_card_or_fetch, obj_ids)))

         
        # for card_id in obj_ids:
        #     # Check if card data is in cache
        #     if fetched_cache and card_id in fetched_cache:
        #         results.append(fetched_cache[card_id])
        #     else:
        #         # Fetch card data from database if not in cache
        #         card_object = Card.objects.get(id=card_id)
        #         serializer = CardSerializer(card_object)
        #         serializer_data = serializer.data
        #         results.append(serializer_data)

        #         # Update cache with new data
        #         if fetched_cache is None:
        #             new_record = {card_id: serializer_data}
        #             cache.set(cache_key, new_record, timeout=REDIS_TIMEOUT)
        #             fetched_cache = new_record
        #         else:
        #             fetched_cache[card_id] = serializer_data
        #             cache.set(cache_key, fetched_cache, timeout=REDIS_TIMEOUT)

        # Prepare the response data
        data_dict = {
            "count": len(results),
            "results": results,
        }

        return Response(data_dict)

    
    # Old card list code ----------
    # def list(self, request, *args, **kwargs):
    #     cache_key = f"{self.request.tenant}_card_model_redis"
    #     type_id = self.request.GET.get("type_id", None)
    #     card_type = self.request.GET.get("card_type", None)
    #
    #     if type_id == "null" and card_type:
    #         queryset = Card.objects.filter(
    #             type__id=None, card_type=str(card_type)
    #         ).select_related("creator", "type").order_by("-created_at")
    #     elif type_id and card_type:
    #         queryset = Card.objects.filter(
    #             type__id=type_id, card_type=str(card_type)
    #         ).select_related("creator", "type").order_by("-created_at")
    #     elif type_id == "null":
    #         queryset = Card.objects.filter(type__id=None).select_related("creator", "type").order_by("-created_at")
    #     elif type_id:
    #         queryset = Card.objects.filter(type__id=type_id).select_related("creator", "type").order_by("-created_at")
    #     elif card_type:
    #         queryset = Card.objects.filter(card_type=str(card_type)).select_related("creator", "type").order_by(
    #             "-created_at"
    #         )
    #     else:
    #         queryset = (
    #             Card.objects.select_related("creator", "type")
    #             .all()
    #             .order_by("-created_at")
    #         )
    #
    #     obj_ids = list(queryset.values_list("id", flat=True))
    #
    #     if cache_key in cache:
    #         check_cache_keys = RedisModel.check_keys(
    #             cache_key=cache_key, keys=obj_ids
    #         )
    #         cache_data_get = RedisModel.filter(cache_key=cache_key, keys=obj_ids)
    #
    #         if len(check_cache_keys) == 0 and cache_data_get:
    #             return Response(data={"count": len(cache_data_get.keys()), "results": cache_data_get.values()})
    #
    #     serializer = self.get_serializer(queryset, many=True)
    #     if serializer.data:
    #         for tdata in serializer.data:
    #             RedisModel.create(cache_key=cache_key, key=tdata["id"], value=tdata)
    #
    #     return Response(data={"count": queryset.count(), "results": serializer.data})

    def perform_create(self, serializer):
        check = user_access_check(user=self.request.user, required_permissions=["READ", "CREATE"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            transaction_point = transaction.savepoint()
            try:
                serializer.save(creator=self.request.user)
                details = serializer.data

                test_send_notification_to_subscribers(
                    tenant=self.request.tenant,
                    user=self.request.user,
                    object_id=details["id"],
                    event_id=7,
                    type="success",
                    detail_url=f"/api/system/card/{details['id']}/",
                    model="card",
                    nt_key=True,
                )

                # card_obj = Card.objects.get(id=details["id"])
                transaction.savepoint_commit(transaction_point)
                # get_custom_activity_logger(
                #     "CREATE", card_obj, self.request.user, "", model="card"
                # )
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
                    request, request.data, old_instance, "card", "MODIFY"
                )
                transaction.savepoint_commit(transaction_point)
                return Response(details)
            except Exception as error:
                transaction.savepoint_rollback(transaction_point)
                return Response({"error": _(str(error))}, status=status.HTTP_400_BAD_REQUEST)   

    def destroy(self, request, *args, **kwargs):
        check = user_access_check(user=self.request.user, required_permissions=["READ", "DELETE"])
        if not isinstance(check, bool):
            return Response(check, status=status.HTTP_400_BAD_REQUEST)
        
        instance = self.get_object()
        self.perform_destroy(instance)

        test_send_notification_to_subscribers(
            tenant=self.request.tenant,
            user=self.request.user,
            object_id=None,
            event_id=8,
            type="success",
            detail_url=None,
            model=None,
            isError=True,
            error_message=f"Card with id: {instance.pk} is deleted successfully.",
        )

        get_custom_activity_logger("DELETE", instance, self.request.user, model="card")

        return Response(
            {"message": "Card is deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )
