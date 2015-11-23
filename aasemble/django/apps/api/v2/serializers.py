from rest_framework import serializers

from aasemble.django.apps.buildsvc import models as buildsvc_models
from aasemble.django.apps.mirrorsvc import models as mirrorsvc_models


class SimpleListField(serializers.ListField):
    child = serializers.CharField()

    def to_internal_value(self, data):
        return ' '.join(data)

    def to_representation(self, data):
        if isinstance(data, list):
            return data
        return data.split(' ')


class MirrorSerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_mirror-detail', read_only=True, source='*', lookup_field='uuid')
    url = serializers.URLField(required=True)
    series = SimpleListField(required=True)
    components = SimpleListField(required=True)
    public = serializers.BooleanField(default=False)
    refresh_in_progress = serializers.BooleanField(read_only=True)

    class Meta:
        model = mirrorsvc_models.Mirror
        fields = ('self', 'url', 'series', 'components', 'public', 'refresh_in_progress')


class MirrorField(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        if hasattr(self, 'context') and 'request' in self.context:
            return mirrorsvc_models.Mirror.objects.filter(owner=self.context['request'].user)

        return super(MirrorField, self).get_queryset()


class MirrorSetSerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_mirrorset-detail', read_only=True, source='*', lookup_field='uuid')
    mirrors = MirrorField(many=True, view_name='v2_mirror-detail', queryset=mirrorsvc_models.Mirror.objects.all(), lookup_field='uuid')

    class Meta:
        model = mirrorsvc_models.MirrorSet
        fields = ('self', 'mirrors')


class MirrorSetField(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        if hasattr(self, 'context') and 'request' in self.context:
            return mirrorsvc_models.MirrorSet.lookup_by_user(self.context['request'].user)

        return super(MirrorSetField, self).get_queryset()


class TagsSerializer(serializers.ListField):
    child = serializers.CharField()

    def to_internal_value(self, data):
        tags = data
        tag_val = []
        for tag in tags:
            tag_val.append(dict(tag=tag))
        return tag_val

    def to_representation(self, data):
        tags = data.all()
        tag_val = []
        for tag in tags:
            tag_val.append(tag.tag)
        return tag_val


class SnapshotSerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_snapshot-detail', read_only=True, source='*', lookup_field='uuid')
    mirrorset = MirrorSetField(view_name='v2_mirrorset-detail', queryset=mirrorsvc_models.MirrorSet.objects.none(), lookup_field='uuid')
    tags = TagsSerializer(required=False)

    class Meta:
        model = mirrorsvc_models.Snapshot
        fields = ('self', 'timestamp', 'mirrorset', 'tags')
 
    def create(self, validated_data):
        if 'tags' in validated_data:
            tags_data = validated_data.pop('tags')
            snapshot = mirrorsvc_models.Snapshot.objects.create(**validated_data)
            for tag_data in tags_data:
                mirrorsvc_models.Tags.objects.create(snapshot=snapshot, **tag_data)
        else:
            snapshot = mirrorsvc_models.Snapshot.objects.create(**validated_data)
        return snapshot

    def update(self, instance, validated_data):
        if 'tags' in validated_data:
            tags_data = validated_data.pop('tags')
            mirrorsvc_models.Tags.objects.filter(snapshot=instance).delete()
            for tag_data in tags_data:
                mirrorsvc_models.Tags.objects.create(snapshot=instance, **tag_data)
        return instance


class RepositoryField(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        if hasattr(self, 'context') and 'request' in self.context:
            return buildsvc_models.Repository.lookup_by_user(self.context['request'].user)

        return super(RepositoryField, self).get_queryset()


class PackageSourceSerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_packagesource-detail', read_only=True, source='*', lookup_field='uuid')
    git_repository = serializers.URLField(source='git_url', required=True)
    git_branch = serializers.SlugField(source='branch', required=True)
    repository = RepositoryField(view_name='v2_repository-detail', source='series.repository', queryset=buildsvc_models.Repository.objects.all(), lookup_field='uuid')
    builds = serializers.HyperlinkedIdentityField(view_name='v2_build-list', lookup_url_kwarg='source_uuid', lookup_field='uuid', read_only=True)

    class Meta:
        model = buildsvc_models.PackageSource
        fields = ('self', 'git_repository', 'git_branch', 'repository', 'builds')

    def validate_repository(self, value):
        return value.first_series()

    def validate(self, data):
        res = super(PackageSourceSerializer, self).validate(data)
        res['series'] = res['series']['repository']
        return res


class SeriesSerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_series-detail', read_only=True, source='*', lookup_field='uuid')

    class Meta:
        model = buildsvc_models.Series
        fields = ('self', 'name', 'repository', 'binary_source_list', 'source_source_list')


class BuildRecordSerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_buildrecord-detail', read_only=True, source='*', lookup_field='uuid')
    source = serializers.HyperlinkedRelatedField(view_name='v2_packagesource-detail', read_only=True, lookup_field='uuid')

    class Meta:
        model = buildsvc_models.BuildRecord
        fields = ('self', 'source', 'version', 'build_started', 'sha', 'buildlog_url')


class ExternalDependencySerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_externaldependency-detail', read_only=True, source='*')
    repository = RepositoryField(view_name='v2_externaldependency-detail', source='own_series.repository', queryset=buildsvc_models.Repository.objects.all())

    class Meta:
        model = buildsvc_models.ExternalDependency
        fields = ('self', 'url', 'series', 'components', 'repository', 'key')

    def validate_repository(self, value):
        return value.first_series()

    def validate(self, data):
        res = super(ExternalDependencySerializer, self).validate(data)
        if 'own_series' in res:
            res['own_series'] = res['own_series']['repository']
        return res


class RepositorySerializer(serializers.HyperlinkedModelSerializer):
    self = serializers.HyperlinkedRelatedField(view_name='v2_repository-detail', read_only=True, source='*', lookup_field='uuid')
    user = serializers.ReadOnlyField(source='user.username')
    key_id = serializers.CharField(read_only=True)
    binary_source_list = serializers.ReadOnlyField(source='first_series.binary_source_list')
    source_source_list = serializers.ReadOnlyField(source='first_series.source_source_list')
    sources = serializers.HyperlinkedIdentityField(view_name='v2_packagesource-list', lookup_url_kwarg='repository_uuid', lookup_field='uuid', read_only=True)
    external_dependencies = serializers.HyperlinkedIdentityField(view_name='v2_externaldependency-list', lookup_url_kwarg='repository_uuid', lookup_field='uuid', read_only=True)

    class Meta:
        model = buildsvc_models.Repository
        fields = ('self', 'user', 'name', 'key_id', 'sources', 'binary_source_list', 'source_source_list', 'external_dependencies')
