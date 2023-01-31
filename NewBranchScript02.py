from extras.scripts import *
from django.utils.text import slugify

from dcim.choices import DeviceStatusChoices, SiteStatusChoices
from dcim.models import Device, DeviceRole, DeviceType, Site, Interface
from ipam.choices import PrefixStatusChoices, VLANStatusChoices
from ipam.models import Prefix, VRF, IPAddress, VLANGroup, VLAN


class NewBranchScript(Script):

    class Meta:
        name = "New Branch"
        description = "Provision a new branch site"

    site_name = StringVar(
        description="Name of the new site",
        default="DEMO"
    )
    site_short = StringVar(
        description="Short name for the new site",
        default="DEM"
    )
    dist_switch_model = ObjectVar(
        description="Distibution switch model",
        model=DeviceType
    )
    switch_count = IntegerVar(
        description="Number of access switches to create",
        default="5"
    )
    switch_model = ObjectVar(
        description="Access switch model",
        model=DeviceType
    )
    router_count = IntegerVar(
        description="Number of routers to create",
        default="2"
    )
    router_model = ObjectVar(
        description="Router model",
        model=DeviceType
    )
    site_id = IntegerVar(
        description="ID number for the new site",
        default="253"
    )
    site_vrf = ObjectVar(
        description="VRF for site prefixes",
        model=VRF
    )

    def run(self, data, commit):

        # Create the new site
        site = Site(
            name=data['site_name'],
            slug=slugify(data['site_name']),
            status=SiteStatusChoices.STATUS_PLANNED
        )
        site.custom_field_data['short'] = data["site_short"]
        site.save()
        self.log_success(f"Created new site: {site}")

        #Create Distribution switch dist_switch_model
        switch_role = DeviceRole.objects.get(name='Site switch')
        switch = Device(
            device_type=data['dist_switch_model'],
            name=f'{data["site_short"].upper()}-DIST10',
            site=site,
            status=DeviceStatusChoices.STATUS_PLANNED,
            device_role=switch_role
        )
        switch.save()
        self.log_success(f"Created new switch: {switch}")
        # Create mangement interface
        interface = Interface(name="Vlan320", type="virtual", device=switch)
        interface.save()
        self.log_success(f"Created new interface: {interface}")
        # Set IP address on MGMT interface
        ipaddr = IPAddress(address=f"10.{data['site_id']}.20.10/24", vrf=data['site_vrf'], assigned_object=interface)
        ipaddr.save()
        self.log_success(f"Created new ip: {ipaddr}")
        # Create Port channel interfaces
        for i in range(1, data['switch_count']+1):
            interface = Interface(name=f"Port-channel{i}", type="lag", device=switch, description=f"{data['site_short'].upper()}-SW{i+10} - LACP")
            interface.save()
            self.log_success(f"Created new interface: {interface}")

        # Create access switches
        for i in range(11, data['switch_count'] + 11):
            switch = Device(
                device_type=data['switch_model'],
                name=f'{data["site_short"].upper()}-SW{i}',
                site=site,
                status=DeviceStatusChoices.STATUS_PLANNED,
                device_role=switch_role
            )
            switch.save()
            self.log_success(f"Created new switch: {switch}")
            # Create mangement interface
            interface = Interface(name="Vlan320", type="virtual", device=switch)
            interface.save()
            self.log_success(f"Created new interface: {interface}")
            # Set IP address on MGMT interface
            ipaddr = IPAddress(address=f"10.{data['site_id']}.20.{i}/24", vrf=data['site_vrf'], assigned_object=interface)
            ipaddr.save()
            self.log_success(f"Created new ip: {ipaddr}")
            interface = Interface(name=f"Port-channel1", type="lag", device=switch, description=f"{data['site_short'].upper()}-RSW10 - LACP")
            interface.save()
            self.log_success(f"Created new interface: {interface}")

        # Create routers
        router_role = DeviceRole.objects.get(name='Site router')
        for i in range(1, data['router_count'] + 1):
            router = Device(
                device_type=data['router_model'],
                name=f'{data["site_short"].upper()}-R{i}',
                site=site,
                status=DeviceStatusChoices.STATUS_PLANNED,
                device_role=router_role,
            )
            router.save()
            self.log_success(f"Created new router: {router}")
            # Create mangement interface
            interface = Interface(name="Loopback0", type="virtual", device=router)
            interface.save()
            # Set IP address on MGMT interface
            ipaddr = IPAddress(address=f"10.0.{data['site_id']}.10{i-1}/32", vrf=data['site_vrf'], assigned_object=interface)
            ipaddr.save()
            router.primary_ip4 = ipaddr
            router.save()
            self.log_success(f"Created new ip: {ipaddr}")

        # Create VLANs and groups
        new_vlan_group = VLANGroup(
            name=f"{data['site_short'].upper()}-VLAN-Group",
            description=f"Vlan Group for {data['site_name']}'",
            #scope_type="dcim.site",
            #scope_id=site.id
        )
        new_vlan_group.save()
        self.log_success(f"Created new VLAN Group: {new_vlan_group}")
        
        vlans = [20,30,40,50,60,70,80,90]
        for vlan in vlans:
            new_vlan = VLAN(
                vid=vlan,
                name=f"VLAN{vlan}",
                site=site,
                status=VLANStatusChoices.STATUS_ACTIVE,
                group=new_vlan_group
            )
            new_vlan.save()
            self.log_success(f"Created new VLAN: {new_vlan}")
            new_prefix = Prefix(prefix=f"10.{data['site_id']}.{vlan-300}.0/24", site=site, status=PrefixStatusChoices.STATUS_ACTIVE, vrf=data['site_vrf'], vlan=new_vlan)
            new_prefix.save()
            self.log_success(f"Created new prefix: {new_prefix}")

        
        # Create prefix
        prefixes = [f"10.{data['site_id']}.0.0/16", f"10.0.{data['site_id']}.0/24"]
        for prefix in prefixes:
            new_prefix = Prefix(
                prefix=prefix,
                site=site,
                status=PrefixStatusChoices.STATUS_ACTIVE,
                vrf=data['site_vrf']
            )
            new_prefix.save()
            self.log_success(f"Created new Prefix: {prefix}")

        # Generate a CSV table of new devices
        output = [
            'name,make,model'
        ]
        for switch in Device.objects.filter(site=site):
            attrs = [
                switch.name,
                switch.device_type.manufacturer.name,
                switch.device_type.model
            ]
            output.append(','.join(attrs))

        return '\n'.join(output)
