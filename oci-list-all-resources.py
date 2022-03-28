import oci
import sys
import csv
import time
import json
import logging
from datetime import datetime as dt
from collections import Counter


recursive_report = True
collect_for_home_region_only = False
props_mapping = {"instance": ['availability_domain', 'capacity_reservation_id','compartment_id','display_name','id','lifecycle_state','region','shape','shape_config.memory_in_gbs','shape_config.ocpus','shape_config.local_disks_total_size_in_gbs','shape_config.local_disk_description'],
           "volume": ['availability_domain','compartment_id','display_name','id','lifecycle_state','vpus_per_gb','size_in_gbs','is_hydrated','is_auto_tune_enabled'],
           "bootvolume":['availability_domain','compartment_id','display_name','id','lifecycle_state','vpus_per_gb','size_in_gbs','is_hydrated','is_auto_tune_enabled']}


def get_logger(logger_name, logLevel):
    print("init logger - name : {} , level : {}".format(logger_name,logLevel))
    log = logging.getLogger(logger_name)
    log.setLevel(logLevel)
    ch = logging.StreamHandler()
    ch.setLevel(logLevel)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %H:%M:%S')
    ch.setFormatter(formatter)
    log.addHandler(ch)
    return log

def get_param_value(obj,param_path,default_value=""):
    try:
        path_parts = param_path.split(".")
        temp = obj
        for part in path_parts:
            if type(temp) is dict:
                temp = temp[part]
            else:
                temp = getattr(temp, part)
            if part == path_parts[-1]:
                return temp
    except Exception as e:
        #log.error("error geting attribute {} for object {} : {}".format(param_path, type(obj), e))
        return default_value



def get_instances_for_compartment(region, compartment_id):
    instances_list = []
    log.info("{} getting instances in : {}".format(region, compartment_id))
    response = compute_client.list_instances(compartment_id)
    instances_list = instances_list + response.data
    while response.has_next_page:
        response = compute_client.list_instances(compartment_id,page=response.next_page)
        instances_list = instances_list + response.data
    instances_list = list(map(lambda n: ("instance",n), instances_list))
    log.info("{} {} instances in : {}".format(region, len(instances_list), compartment_id))
    return instances_list

def get_bootvolumes_for_compartment(region, compartment_id):
    bootvolumes_list_all = []
    response_availability_domains = identity_client.list_availability_domains(compartment_id)

    for availability_domain in response_availability_domains.data:
        bootvolumes_list = []
        log.info("{} {} getting bootvolumes in : {}".format(region,availability_domain.name, compartment_id))
        response = block_client.list_boot_volumes(availability_domain = availability_domain.name, compartment_id = compartment_id)
        bootvolumes_list = bootvolumes_list + response.data
        while response.has_next_page:
            response = block_client.list_boot_volumes(availability_domain = availability_domain.name, compartment_id = compartment_id, page=response.next_page)
            bootvolumes_list = bootvolumes_list + response.data
        log.info("{} {} {} bootvolumes in : {}".format(region,availability_domain.name,len(bootvolumes_list), compartment_id))
        bootvolumes_list_all = bootvolumes_list_all + bootvolumes_list

    bootvolumes_list_all = list(map(lambda n: ("bootvolume",n), bootvolumes_list_all))
    return bootvolumes_list_all

def get_blockvolumes_for_compartment(region, compartment_id):
    blockvolumes_list = []
    # response_availability_domains = identity_client.list_availability_domains(compartment_id)
    # for availability_domain in response_availability_domains.data:
    log.info("{} getting blockvolumes in : {}".format(region, compartment_id))
    # response = block_client.list_volumes(availability_domain = availability_domain, compartment_id = compartment_id)
    response = block_client.list_volumes( compartment_id = compartment_id)
    blockvolumes_list = blockvolumes_list + response.data
    while response.has_next_page:
        # response = block_client.list_volumes(availability_domain = availability_domain, compartment_id = compartment_id,page=response.next_page)
        response = block_client.list_volumes(compartment_id = compartment_id,page=response.next_page)
        blockvolumes_list = blockvolumes_list + response.data

    log.info("{} {} blockvolumes in : {}".format(region, len(blockvolumes_list), compartment_id))
    blockvolumes_list = list(map(lambda n: ("volume",n), blockvolumes_list))
    return blockvolumes_list

def get_resources_for_compartment(region, compartment_id):
    resources_list = []

    try:
        response_compartments = identity_client.list_compartments(compartment_id)
        #print(response_compartments.data)
        for compartment in response_compartments.data:
            compartments_dict[compartment.id] = compartment
            if recursive_report:
                resources_list = resources_list + get_resources_for_compartment(region, compartment.id)
    except Exception as e:
         log.error("error geting compartment for {} : {}".format(compartment_id, e))
         return []
    
    #return all resources in compartment_id
    log.info("{} resources in : {}".format(region, compartment_id))
    resources_list = resources_list + get_instances_for_compartment(region, compartment_id)
    resources_list = resources_list + get_bootvolumes_for_compartment(region, compartment_id)
    resources_list = resources_list + get_blockvolumes_for_compartment(region, compartment_id)
    #todo:
    #add boot backups
    #add vnics
    #add object storage
    #add network

    return resources_list

if __name__ == "__main__":
    log = get_logger("GetAllResources",5)  

    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    
    #dict to store all compartments for output
    compartments_dict = dict()
    tenancy_id = signer.tenancy_id
    compartment_id = sys.argv[1] if len(sys.argv) == 2 else tenancy_id

    log.info("tenancy_id : {}".format(tenancy_id))
    log.info("compartment_id : {}".format(compartment_id))
    log.info("recursive_report : {}".format(recursive_report))
    log.info("collect_for_home_region_only : {}".format(collect_for_home_region_only))

    
    identity_client = oci.identity.IdentityClient(config={}, signer=signer)
    subscriptions = identity_client.list_region_subscriptions(tenancy_id)

    #add requested compartment in to dictionary
    compartments_dict[compartment_id] = identity_client.get_compartment(compartment_id).data


    resources_list = []
    for subscription in subscriptions.data:
        if collect_for_home_region_only and not subscription.is_home_region:
            continue
        compute_client = oci.core.ComputeClient(config={"region":subscription.region_name}, signer=signer)
        identity_client = oci.identity.IdentityClient(config={"region":subscription.region_name}, signer=signer)
        block_client = oci.core.BlockstorageClient(config={"region":subscription.region_name}, signer=signer)
        #resource_search_client = oci.resource_search.ResourceSearchClient(config={"region":subscription.region_name}, signer=signer)
        resources_list = resources_list + get_resources_for_compartment(subscription.region_name,compartment_id)


    file_name_prefix = str(dt.now().strftime("%Y%m%d-%H%M"))
    file_name = file_name_prefix + "_resources.csv"

    #props list:
    shared_properties_list = []
    specific_properties_list = []
    for prop_list in props_mapping.values():
        for prop in prop_list:
            if not prop in shared_properties_list and not prop in specific_properties_list:
                shared = True
                for prop1_list in props_mapping.values():
                    if not prop in prop1_list:
                        specific_properties_list.append(prop)
                        shared = False
                        break
                if shared:
                    shared_properties_list.append(prop)
    properties_list = shared_properties_list + specific_properties_list

    #properties_list = list(set([item for sublist in props_mapping.values() for item in sublist]))

    # compartments names
    #compartments_dict = {compartment.id:compartment.name for compartment in compartments_set}

    
    log.info("props : {}".format(properties_list))
    with open(file_name, 'w',) as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow( ["resource_type","prefix","compartment_name"]+ properties_list)
        for resource in resources_list:
            output = []
            output.append(resource[0])
            output.append(file_name_prefix)
            #extract compartment name
            v1 = get_param_value(resource[1],"compartment_id")
            v2 = compartments_dict.get(v1,"")
            output.append(v2.name)
            for prop in properties_list:
                output.append(get_param_value(resource[1],prop))
            writer.writerow(output)


    