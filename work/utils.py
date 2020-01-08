from work.models import Ocp_Skill_Type, Ocp_Artwork_Type
from general.models import Artwork_Type, Job, UnitRatio
from django.forms import ValidationError
from django.conf import settings

import decimal
import requests
import logging
logger = logging.getLogger("ocp")

if "pinax.notifications" in settings.INSTALLED_APPS:
    from pinax.notifications import models as notification
    from pinax.notifications.hooks import hookset
else:
    notification = None


if hasattr(settings, 'DECIMALS'):
    DECIMALS = settings.DECIMALS
else:
    DECIMALS = decimal.Decimal('1.000000000')

def get_rt_from_ocp_rt(gen_rt):
    rt = None
    if hasattr(gen_rt, 'resource_type') and gen_rt.resource_type:
        rt = gen_rt.resource_type
    else:
        if isinstance(gen_rt, Artwork_Type):
            try:
                grt = Ocp_Artwork_Type.objects.get(id=gen_rt.id)
                rt = grt.resource_type
            except:
                rt = False
    return rt

def get_ocp_rt_from_rt(rt):
    gen_rt = None
    if hasattr(rt, 'ocp_resource_type') and rt.ocp_resource_type:
        gen_rt = rt.ocp_resource_type
    else:
        try:
            gen_rt = Ocp_Artwork_Type.objects.get(resource_type=rt)
        except:
            gen_rt = False
    return gen_rt


def get_rt_from_ocp_st(gen_st):
    rt = None
    if hasattr(gen_st, 'resource_type') and gen_st.resource_type:
        rt = gen_st.resource_type
    else:
        if isinstance(gen_st, Ocp_Skill_Type):
            try:
                gst = Ocp_Skill_Type.objects.get(id=gen_st.id)
                rt = gst.resource_type
            except:
                rt = False
    return rt

def get_ocp_st_from_rt(rt):
    gen_st = None
    if hasattr(rt, 'ocp_skill_type') and rt.ocp_skill_type:
        gen_st = rt.ocp_skill_type
    else:
        try:
            gen_st = Ocp_Skill_Type.objects.get(resource_type=rt)
        except:
            gen_st = False
    return gen_st


def set_user_notification_by_type(user, notification_type="work_new_account", send=True):
    sett = None
    if notification:
        nott = notification.NoticeType.objects.get(label=notification_type)
        sett = user.noticesetting_set.filter(notice_type=nott)
        if not sett:
            for medium_id, medium_display in notification.NOTICE_MEDIA:
                if medium_display == 'email':
                    medium = medium_id, medium_display
                    sett = hookset.notice_setting_for_user(user, nott, medium_id)
        else:
            if not len(sett) == 1:
                raise ValidationError("(set_user_notification_by_type) The user has not exactly 1 notice setting for the notice type: "+str(notification_type)+" / User: "+str(user))
            sett = sett[0]
        sett.send = send
        sett.save()
    return sett


def convert_price(amount, shunit, unit, obj=None, deci=9):
    if not amount: raise ValidationError("Convert_price without amount? unit1:"+str(shunit)+" unit2:"+str(unit))
    if not shunit: raise ValidationError("Convert_price without unit1? amount:"+str(amount)+" unit2:"+str(unit))
    if not unit: raise ValidationError("Convert_price without unit2? amount:"+str(amount)+" unit1:"+str(shunit))
    ratio = None
    price = None
    if amount and shunit and unit:
        if not shunit == unit:
            if not isinstance(amount, decimal.Decimal) and not isinstance(amount, int): # == 'int':
                raise ValidationError("Amount should be a Decimal or Integer! type:"+str(type(amount)))
            elif isinstance(amount, int):
                amount = decimal.Decimal(amount)
            try:
                ratio = UnitRatio.objects.get(in_unit=shunit.gen_unit, out_unit=unit.gen_unit).rate
                price = amount/ratio
            except:
                print "No UnitRatio with in_unit '"+str(shunit.gen_unit.name)+"' and out_unit: "+str(unit.gen_unit.name)+". Trying reversed..."
                #logger.info("No UnitRatio with in_unit 'faircoin' and out_unit: "+str(unit.gen_unit)+". Trying reversed...")
                try:
                    ratio = UnitRatio.objects.get(in_unit=unit.gen_unit, out_unit=shunit.gen_unit).rate
                    price = amount*ratio
                except:
                    print "No UnitRatio with out_unit '"+str(shunit.gen_unit.name)+"' and in_unit: "+str(unit.gen_unit.name)+". Trying via botc api..."
                    logger.info("No UnitRatio with out_unit '"+str(shunit.gen_unit.name)+"' and in_unit: "+str(unit.gen_unit.name)+". Trying via botc api...")

                    if 'multicurrency' in settings.INSTALLED_APPS:
                        if 'url_ticker' in settings.MULTICURRENCY:
                            url = settings.MULTICURRENCY['url_ticker']+shunit.abbrev
                            key = unit.abbrev.upper()+'x'+shunit.abbrev.upper()
                            #print("KEY: "+key+" URL:"+url) #+" unitjson:"+str(unit.json))
                            deci = settings.CRYPTO_DECIMALS
                            if obj and not hasattr(obj, 'ratio'):
                              ticker = requests.get(url)
                              if int(ticker.status_code) == 200:
                                json = ticker.json()
                                print("Retrieved the ticker JSON! "+str(json))
                                logger.info("Retrieved the ticker JSON! ") #+str(json))
                                if 'data' in json: #.status == "ok":
                                    if key in json['data']:
                                        decimal.getcontext().prec = deci
                                        ratio = decimal.Decimal(str(json['data'][key]))
                                    else:
                                        print("no key in ticker? "+key+" data:"+str(json['data']))
                                        logger.error("no key in ticker? "+key+" data:"+str(json['data']))
                                else:
                                    print("No ticker.data?? json:"+str(json))
                                    logger.error("No ticker.data?? json:"+str(json))
                              else:
                                error = str(ticker.status_code)
                                msg = ticker.text
                                print("Ticker request have returned "+error+" status code. Error: "+msg)
                                logger.error("Ticker request have returned "+error+" status code. Error: "+msg)
                            else:
                              ratio = obj.ratio
                              print("Using CACHED ratio!!")
                              logger.info("Using CACHED ratio!!")

                            if ratio:
                                price = amount/ratio
                            else:
                                print("No RATIO?? "+str(ratio))
                                logger.error("No RATIO?? "+str(ratio))

                        else:
                            print("No url for the Ticker?")
                            logger.error("No url for the Ticker?")

            if not ratio or not price:
                print("ERROR: ratio:"+str(ratio)+" price:"+str(price))
                raise ValidationError("Can't find the UnitRatio to convert the price to "+str(unit.gen_unit)+" from "+str(shunit))
            else:
                if not isinstance(price, decimal.Decimal) and not isinstance(price, int):
                    raise ValidationError("the price is not a decimal nor int? "+str(type(price)))
                elif isinstance(price, int):
                    amount = price
                else:
                    #decs = decimal.getcontext().prec
                    amount = round(price, deci)

                print "Convert_price: ratio:"+str(ratio)+" price:"+str(price)+" shunit:"+str(shunit)+" unit:"+str(unit)+" amount:"+str(amount)
        else:
            print "Skip convert price, same unit: "+str(unit)
        return amount, ratio
    else:
        raise ValidationError("Convert_price without amount, unit1 or unit2 ??")
        return False


def remove_exponent(num):
    if not isinstance(num, float):
      if '.' in str(num):
        return num.to_integral() if num == num.to_integral() else num.normalize()
    else:
        print("Is a FLOAT??")
    return num



"""
def init_resource_types():
  news = ['news:']
  updt = ['updt:']
  errs = ['errs:']
  typ = Artwork_Type.objects.get(clas='Resource')
  artwks = Artwork_Type.objects.filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
  ocprts = Ocp_Artwork_Type.objects.all()
  if artwks.count() > ocprts.count():
    mtyp = Artwork_Type.objects.get(clas='Material')
    mts = Artwork_Type.objects.filter(lft__gte=mtyp.lft, rght__lte=mtyp.rght, tree_id=mtyp.tree_id)
    ocpmts = Ocp_Material_Type.objects.all()
    for ot in ocpmts:
      try:
        qst = Ocp_Artwork_Type.objects.filter(id=ot.id).update(
            artwork_type = ot.material_type,
            facet_value = ot.facet_value,
            resource_type = ot.resource_type
        )
        if qst.count():
          updt.append(qst.get().name)
        else:
          errs.append('?'+ot.name)
      except:
          aty = Artwork_Type.objects.get(id=ot.id)
        #try:
          #aty = Artwork_Type.objects.get(id=ot.id)
          qst = Ocp_Artwork_Type.objects.create(
            artwork_type = aty.typ_id,
            #artwork_type_ptr_id = aty.id,
            #typ_id = aty.typ_id,
            #name = aty.name,
            #description = aty.description,
            #clas = aty.clas,
            #facet_value = ot.facet_value,
            #resource_type = ot.resource_type
          )
          if qst.count():
            news.append('*'+qst.get().name)
          else:
            errs.append('Q:'+str(qst))
        #except:
        #  errs.append('a:'+aty.name)

    ocpnts = Ocp_Nonmaterial_Type.objects.all()
    for ot in ocpnts:
      try:
        qst = Ocp_Artwork_Type.objects.filter(id=ot.id).update(
            artwork_type = ot.material_type,
            facet_value = ot.facet_value,
            resource_type = ot.resource_type
        )
        if qst.count():
          updt.append(qst.get().name)
        else:
          errs.append('?'+ot.name)
      except:
        try:
          aty = Artwork_Type.objects.get(id=ot.id)
          qst = Ocp_Artwork_Type.objects.create(
            artwork_type = aty,
            facet_value = ot.facet_value,
            resource_type = ot.resource_type
          )
          if qst.count():
            news.append(qst.get().name)
          else:
            errs.append('A:'+aty.name)
        except:
          errs.append(ot.name)

    news.extend(updt)
    news.extend(errs)
    return ', '.join(news)
  else:
    return 'clean'


def update_from_general(clas=None):
  news = ['news:']
  updt = ['updt:']
  if clas == "Material_Type":
    try:
      gen_mts = Material_Type.objects.all() #filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
      ocp_mts = Ocp_Material_Type.objects.all() #filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
      for mt in gen_mts:
        if not mt in ocp_mts:
          obj = Ocp_Material_Type.objects.create( #mt )
            material_type = mt,
            #id=mt.id,
            name=mt.name,
            description=mt.description,
            parent=mt.parent
          ).get()
          news.append(obj)
          #break
        else:
          #pass
          obj = Ocp_Material_Type.objects.filter(id=mt.id).update( #mt )
            #id=mt.id,
            name=mt.name,
            description=mt.description,
           #lft=mt.lft,
           #rght=mt.rght,
           #tree_id=mt.tree_id,
            parent=mt.parent
          ).get()
          updt.append(obj) #.append(update)
      return news.append(updt)
    except:
      pass

  elif clas == "Nonmaterial_Type":
    try:
      gen_nts = Nonmaterial_Type.objects.all() #filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
      ocp_nts = Ocp_Nonmaterial_Type.objects.all() #filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
      for nt in gen_nts:
        if not nt in ocp_nts:
          obj = Ocp_Nonmaterial_Type.objects.create( #nt )
            nonmaterial_type = nt,
            #id=nt.id,
            name=nt.name,
            description=nt.description,
            parent=nt.parent
          ).get()
          news.append(obj)
          #break
        else:
          #pass
          obj = Ocp_Nonmaterial_Type.objects.filter(id=nt.id).update( #nt )
            #id=nt.id,
            name=nt.name,
            description=nt.description,
            parent=nt.parent
          ).get()
          updt.append(obj)
      return news.append(updt)
    except:
      return 'error'
  elif clas == "Skill_Type":
    #try:
      gen_sts = Job.objects.all() #filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
      ocp_sts = Ocp_Skill_Type.objects.all() #filter(lft__gte=typ.lft, rght__lte=typ.rght, tree_id=typ.tree_id)
      for st in gen_sts:
        if not st in ocp_sts:
          obj = Ocp_Skill_Type.objects.create(#st).get()
            #job_id=st.pk,
            id=st.id,
            name=st.name,
            description=st.description,
            parent=st.parent,
            verb=st.verb,
            gerund=st.gerund
          ).get()
          news.append(obj)
          #break
        else:
          #pass
          obj = Ocp_Skill_Type.objects.filter(id=st.id).update( #st )
            #id=st.id,
            name=st.name,
            description=st.description,
            parent=st.parent,
            verb=st.verb,
            gerund=st.gerund
          ).get()
          updt.append(obj)
      return news.append(updt)
    #except:
    #  return 'error'
  else:
    return clas
"""
