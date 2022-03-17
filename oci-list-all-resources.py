import oci
import sys
import csv
import time

import logging

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

def get_param_value(obj,param_path,default_value=None):
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
        log.error("error geting attribute {} for object {} : {}".format(param_path, type(obj), e))
        return default_value



def get_instances_for_compartment(compartment_id):
    instances_list = []
    log.info("instances in : {}".format(compartment_id))
    try:
        response_compartments = identity_client.list_compartments(compartment_id)
        for compartment in response_compartments.data:
            instances_list = instances_list + get_instances_for_compartment(compartment.id)
    except Exception as e:
         log.error("error geting compartment for {} : {}".format(compartment_id, e))
         return []

    # time.sleep(.05)
    #get instances for compartment
    response = compute_client.list_instances(compartment_id)
    instances_list = instances_list + response.data
    while response.has_next_page:
        # time.sleep(.05)
        response = compute_client.list_instances(compartment_id,page=response.next_page)
        instances_list = instances_list + response.data
    return instances_list

def get_resources_for_compartment(region, compartment_id):
    resources_list = []

    try:
        response_compartments = identity_client.list_compartments(compartment_id)
        for compartment in response_compartments.data:
            resources_list = resources_list + get_resources_for_compartment(region, compartment.id)
    except Exception as e:
         log.error("error geting compartment for {} : {}".format(compartment_id, e))
         return []
    
    #return all resources in compartment_id
    log.info("{} resources in : {}".format(region, compartment_id))

    

    return resources_list

if __name__ == "__main__":
    log = get_logger("GetAllResources",5)  

    signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
    compute_client = oci.core.ComputeClient(config={}, signer=signer)
    identity_client = oci.identity.IdentityClient(config={}, signer=signer)
    
    tenancy_id = signer.tenancy_id
    log.info("tenancy_id : {}".format(tenancy_id))
    compartment_id = sys.argv[1] if len(sys.argv) == 2 else tenancy_id
    log.info("compartment_id : {}".format(compartment_id))  
    
    
    subscriptions = identity_client.list_region_subscriptions(tenancy_id)
    resources_list = []
    for subscription in subscriptions.data:
        compute_client = oci.core.ComputeClient(config={"region":subscription.region_name}, signer=signer)
        identity_client = oci.identity.IdentityClient(config={"region":subscription.region_name}, signer=signer)
        resources_list = resources_list + get_resources_for_compartment(subscription.region_name,compartment_id)

    