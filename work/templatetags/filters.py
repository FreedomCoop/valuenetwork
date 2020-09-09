from django import template

register = template.Library()

@register.filter
def reqs_related_agent(jn_reqs, agent):
    if jn_reqs and agent:
        reqs = []
        for req in jn_reqs:
            if hasattr(agent, 'project') and req.project.agent == agent:
                reqs.append(req)
                #print("found project related join_request! "+str(req))
            elif req.agent == agent:
                reqs.append(req)
                #print("found agent related join_request! "+str(req))
        return reqs
    else:
        return jn_reqs

@register.filter
def shares_related_project(shares, project):
    total = 0
    if shares and project:
        acc = project.shares_account_type()
        for sh in shares:
            if sh.resource_type == acc:
                total += sh.price_per_unit

            if hasattr(sh.resource_type, 'ocp_artwork_type') and hasattr(acc, 'ocp_artwork_type'):
                if sh.resource_type.ocp_artwork_type == acc.ocp_artwork_type.rel_nonmaterial_type:
                    total += sh.quantity
        return int(total)
    return False

@register.filter
def show_name(obj, agent):
    return obj.show_name(agent)
