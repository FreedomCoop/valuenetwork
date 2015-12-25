from django.contrib.auth.models import User, Group
from rest_framework import serializers

from valuenetwork.valueaccounting.models import *

class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('api_url', 'username', 'email', 'groups')


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ('api_url', 'name')
        
class EconomicAgentSerializer(serializers.HyperlinkedModelSerializer):
    agent_type = serializers.RelatedField()
    projects = serializers.Field(source='contexts_participated_in')
    class Meta:
        model = EconomicAgent
        fields = ('api_url', 'url', 'name', 'nick', 'agent_type', 'address', 'email', 'projects')
        
class ContextSerializer(serializers.HyperlinkedModelSerializer):
    agent_type = serializers.RelatedField()
    class Meta:
        model = EconomicAgent
        fields = ('api_url', 'url', 'name', 'agent_type', 'address',)
        
        
class AgentTypeSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = AgentType
        fields = ('api_url', 'name', 'party_type', )

class PeopleSerializer(serializers.HyperlinkedModelSerializer):
    agent_type = serializers.RelatedField()
    #projects = serializers.Field(source='contexts_participated_in')
    projects = ContextSerializer(source='contexts_participated_in', many=True)
    class Meta:
        model = EconomicAgent
        fields = ('api_url', 'url', 'name', 'nick', 'agent_type', 'address', 'email', 'projects')
        