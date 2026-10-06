from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from netbox.views import generic
from netbox.ui import layout, panels
from utilities.views import ViewTab, register_model_view

from dcim.models import Device, Module
from netbox_lifecycle.models import (
    LicenseAssignment,
    SupportContractAssignment,
    hardware,
)
from netbox_lifecycle.template_content import (
    get_contract_panel,
    get_license_panel,
)
from netbox_lifecycle.ui import (
    HardwareLifecycleDatesPanel,
    HardwareLifecyclePanel,
)
from virtualization.models import VirtualMachine

PLUGIN_SETTINGS = settings.PLUGINS_CONFIG.get('netbox_lifecycle', {})

__all__ = (
    'DeviceSupportTabView',
    'ModuleSupportTabView',
    'VirtualMachineSupportTabView',
)

# The Support tab is populated with whichever features the operator has
# pointed at it via the *_card_position settings accepting 'tab' (along
# side the classic left_page/right_page/full_width_page card positions).
FIELD_NAMES = {
    'device': 'device_id',
    'module': 'module_id',
    'virtualmachine': 'virtual_machine_id',
}

# ORM filter field per model (SupportContractAssignment / LicenseAssignment FKs)
FK_NAMES = {
    'device': 'device',
    'module': 'module',
    'virtualmachine': 'virtual_machine',
}

LIFECYCLE_SOURCE = {
    # Hardware lifecycle records attach to the *type* on device/module pages
    'device': ('devicetype', 'device_type_id'),
    'module': ('moduletype', 'module_type_id'),
}


def _model_name(instance):
    return instance._meta.model_name


def _assignment_badge(instance):
    return SupportContractAssignment.objects.filter(
        **{FK_NAMES[_model_name(instance)]: instance}
    ).count()


def _has_support_content(instance):
    """
    Tab visibility: at least one feature configured for the tab has data
    to show. Contract/license presence is per-object; the hardware
    lifecycle lives on the object's type.
    """
    name = _model_name(instance)
    fk = FK_NAMES[name]
    if (
        PLUGIN_SETTINGS.get('contract_card_position') == 'tab'
        and SupportContractAssignment.objects.filter(**{fk: instance}).exists()
    ):
        return True
    if (
        PLUGIN_SETTINGS.get('license_card_position') == 'tab'
        and LicenseAssignment.objects.filter(**{fk: instance}).exists()
    ):
        return True
    if (
        PLUGIN_SETTINGS.get('lifecycle_card_position') == 'tab'
        and name in LIFECYCLE_SOURCE
    ):
        app_label, object_id_attr = LIFECYCLE_SOURCE[name]
        content_type = ContentType.objects.get(app_label='dcim', model=app_label)
        return hardware.HardwareLifecycle.objects.filter(
            assigned_object_id=getattr(instance, object_id_attr, instance.id),
            assigned_object_type_id=content_type.id,
        ).exists()
    return False


class LifecycleInfoPanel(panels.Panel):
    """
    Both hardware-lifecycle attribute panels rendered against the
    lifecycle record of the object's type (mirrors LifecycleMixin's
    card rendering for placement inside a layout).
    """

    def __init__(self, lifecycle_app_label, object_id_attr):
        self.lifecycle_app_label = lifecycle_app_label
        self.object_id_attr = object_id_attr
        super().__init__()

    def render(self, context):
        instance = context.get('object')
        content_type = ContentType.objects.get(
            app_label='dcim', model=self.lifecycle_app_label
        )
        lifecycle = hardware.HardwareLifecycle.objects.filter(
            assigned_object_id=getattr(instance, self.object_id_attr, instance.id),
            assigned_object_type_id=content_type.id,
        ).first()
        context = {**context, 'object': lifecycle}
        return mark_safe(
            HardwareLifecyclePanel().render(context)
            + HardwareLifecycleDatesPanel().render(context)
        )


def _support_layout(model_name):
    left = []
    right = []
    if PLUGIN_SETTINGS.get('contract_card_position') == 'tab':
        left.append(get_contract_panel(model_name, FIELD_NAMES[model_name]))
    if PLUGIN_SETTINGS.get('license_card_position') == 'tab':
        right.append(get_license_panel(model_name, FIELD_NAMES[model_name]))
    if (
        PLUGIN_SETTINGS.get('lifecycle_card_position') == 'tab'
        and model_name in LIFECYCLE_SOURCE
    ):
        right.append(LifecycleInfoPanel(*LIFECYCLE_SOURCE[model_name]))
    return layout.SimpleLayout(left_panels=left, right_panels=right)


# Views ------------------------------------------------------------------


class BaseSupportTabView(generic.ObjectView):
    template_name = 'generic/object.html'
    actions = ()


@register_model_view(Device, 'support', path='support')
class DeviceSupportTabView(BaseSupportTabView):
    queryset = Device.objects.all()
    layout = _support_layout('device')
    tab = ViewTab(
        label=_('Support'),
        visible=_has_support_content,
        badge=_assignment_badge,
        permission='netbox_lifecycle.view_supportcontractassignment',
    )


@register_model_view(Module, 'support', path='support')
class ModuleSupportTabView(BaseSupportTabView):
    queryset = Module.objects.all()
    layout = _support_layout('module')
    tab = ViewTab(
        label=_('Support'),
        visible=_has_support_content,
        badge=_assignment_badge,
        permission='netbox_lifecycle.view_supportcontractassignment',
    )


@register_model_view(VirtualMachine, 'support', path='support')
class VirtualMachineSupportTabView(BaseSupportTabView):
    queryset = VirtualMachine.objects.all()
    layout = _support_layout('virtualmachine')
    tab = ViewTab(
        label=_('Support'),
        visible=_has_support_content,
        badge=_assignment_badge,
        permission='netbox_lifecycle.view_supportcontractassignment',
    )
