function cleantypename(str){
    return str.split('. ').join('');
}

$(document).ready(function(){


    //   M O D A L S

    /* // the model of the js object in the template
    var R_{{ node.id }}_obj = {
        "name":"{{ node.resource_type.name }}",
        "parent":"{{ node.parent.id }}",
        "description":"{{ node.resource_type.description }}",
        "context":"{{ node.resource_type.context_agent.id }}",
        "substi":"{{ node.resource_type.substitutable }}",
        "unit":"{{ node.resource_type.unit.id }}",
        "price":"{{ node.resource_type.price_per_unit }}",
        "related":"{{ node.resource_type.related_type.id }}",
        "parentrecipe":"{{ node.resource_type.parent.id }}",
        "url":"{{ node.resource_type.url }}",
        "photo_url":"{{ node.resource_type.photo_url }}"
        {% if request.user.is_staff %}
          {% if not node.facet_value and not node.facet %}"n_desc" : "{{ node.get_descendant_count }}",{% endif %}
          {% if node.facet_value %}"fv" : "{{ node.facet_value.value|upper }}",
          {% elif node.facet %}"fv" : "{{ node.facet|upper }}",
          {% elif node.resource_type.facets %}"fv" : "{{ node.resource_type.facet_values_list }}",{% endif %}
        {% endif %}
    };
    */

    var old_agent = false;
    var old_rt = false;
    var old_st = false;
    var old_unit = false;
    var old_related = false;
    var old_parent = false;
    var old_et = false;

    function rebuild_modal(tid){
      var ide = false;
      if( typeof tid == 'undefined' ) { alert("rebuild_modal: No tid"); }
      else if( tid == "resource_type" ) {
        var tree = $('#resource_type_tree').first();
        var node = tree.fancytree("getTree").getActiveNode();
        //alert('tree:'+tree.fancytree("getTree"));//+' node:'+node.key+' sel:'+node.isSelected());
        if(node && node.isSelected()){
          ide = node.key;
        }
      } else if( tid == "skill_type" ) {
        tree = $('#skill_type_tree').first();
        node = tree.fancytree("getTree").getActiveNode();
        if(node && node.isSelected()){
          ide = node.key;
        }
      } else if( tid == "exchange_type" ) {
        tree = $('.exchange_type_tree:visible').first();
        node = tree.fancytree("getTree").getActiveNode();
        if(node && node.isSelected()){
          ide = node.key;
        }
      } else {
        alert('tid? '+tid);
      }
      if( !ide || !tid ) {
        alert('rebuild_modal: IDE:'+ide+' tid:'+tid+' tree:'+tree.attr('class')+' node:'+node)
      }

      var idarr = ide.split('_');
      if( tid == "resource_type" && typeof eval('R_'+idarr[1]+'_obj') != "undefined" ){//&& $('input[name=new_resource_type]').length ) {
        var obj = eval('R_'+idarr[1]+'_obj');
      } else if( tid == "skill_type" && typeof eval('S_'+idarr[1]+'_obj') != "undefined" ){//&& $('input[name=new_skill_type]').length ) {
        var obj = eval('S_'+idarr[1]+'_obj');
      } else if( tid == "exchange_type" && typeof eval('E_'+idarr[1]+'_obj') != "undefined" ){//&& $('input[name=new_skill_type]').length ) {
        var obj = eval('E_'+idarr[1]+'_obj');
      } else {
        alert("rebuild_modal: No OBJ! tid:"+tid+" ide:"+ide);
      }
      var name = obj['name'];
      var $mod = false;
      //alert('obj: '+obj['name']);
      if( idarr[0] == "Rid" ) {
        $mod = $('#addResourceTypeModal');
      };
      if( idarr[0] == "Sid" ) {
        $mod = $('#addSkillTypeModal');
      };
      if( idarr[0] == "Eid" ) {
        $mod = $('#editExchangeTypeModal');
      };
      //ide = idarr[1];
      if($mod){
        $mod.find('#name_action').text("Edit \""+name+'"');
        $mod.find('#id_name').val(name);
        if(obj['description']) $mod.find('#id_description').val(obj['description'].split('<br>').join('\n'));
        if(obj['substi'] == 'False' || obj['substi'] == '') $mod.find('#id_substitutable').val(obj['substi']).prop('checked', false);
        else if(obj['substi'] && obj['substi'] == 'True') $mod.find('#id_substitutable').val(obj['substi']).prop('checked', true);
        $mod.find('#id_substitutable').change(function(){
          if($(this).prop('checked')) $(this).val('True');
          else $(this).val('False');
        });
        $mod.find('#id_price_per_unit').val(obj['price']);
        $mod.find('#id_url').val(obj['url']);
        $mod.find('#id_photo_url').val(obj['photo_url']);

        var restyp = tid=="exchange_type" ? obj['resource_type'] : obj['parent'];
        if( tid == "resource_type" || tid == "exchange_type" ) {
          $mod.find('#id_resource_type option').each(function(){
            if($(this).prop('selected')) old_rt = $(this).val();
            $(this).prop('selected', false);
            if($(this).val() == restyp){
              $(this).prop('selected', true); //alert('Hau!:'+$(this).val());
            }
          });
          if(!old_rt || old_rt != restyp) $mod.find('#id_resource_type').trigger("chosen:updated");
        }
        var skityp = tid=="exchange_type" ? obj['skill_type'] : obj['parent'];
        if( tid == "skill_type" ) {
          $mod.find('#id_verb').val(obj['verb']);
          $mod.find('#id_gerund').val(obj['gerund']);
          $mod.find('#id_parent_type option').each(function(){
            if($(this).prop('selected')) old_st = $(this).val();
            $(this).prop('selected', false);
            if($(this).val() == skityp){
              $(this).prop('selected', true); //alert('Hau!:'+$(this).val());
            }
          });
          if(!old_st || old_st != skityp) $mod.find('#id_parent_type').trigger("chosen:updated");
        } else if( tid == "exchange_type" ) {
          $mod.find('#id_skill_type option').each(function(){
            if($(this).prop('selected')) old_st = $(this).val();
            $(this).prop('selected', false);
            if($(this).val() == skityp){
              $(this).prop('selected', true); //alert('Hau!:'+$(this).val());
            }
          });
          if(!old_st || old_st != skityp) $mod.find('#id_skill_type').trigger("chosen:updated");
        }
        $mod.find('#id_context_agent option').each(function(){
          if(obj['context']){
            if($(this).prop('selected')) old_agent = $(this).val();
            $(this).prop('selected', false);
            //alert('hey: '+$(this).val()+' context:'+obj['context']);
            if($(this).val() == obj['context']){
              $(this).prop('selected',true);
            }
          }
          //alert('context: '+obj['context']);
        });
        if(!old_agent || old_agent != obj['context']) $mod.find('#id_context_agent').trigger("chosen:updated");

        $mod.find('#id_unit_type option').each(function(){
          if($(this).prop('selected')) old_unit = $(this).val();
          $(this).prop('selected', false);
          if($(this).val() == obj['unit']){
            //alert('hey: '+$(this).val()+' unit:'+obj['unit']);
            $(this).prop('selected',true);
          }
        });
        if(!old_unit || old_unit != obj['unit']) $mod.find('#id_unit_type').trigger("chosen:updated");

        //alert('related: '+obj['related']);
        $mod.find('#id_related_type option').each(function(){
          if($(this).prop('selected')) old_related = $(this).val();
          $(this).prop('selected', false);
          if($(this).val() == obj['related']){
            //alert('hey: '+$(this).val()+' related:'+obj['related']);
            $(this).prop('selected',true);
          }
        });
        if(!old_related || old_related != obj['related']) $mod.find('#id_related_type').trigger("chosen:updated");

        $mod.find('#id_parent option').each(function(){
          if($(this).prop('selected')) old_parent = $(this).val();
          $(this).prop('selected', false);
          if($(this).val() == obj['parentrecipe']){
            //alert('hey: '+$(this).val()+' parent-recipe:'+obj['parentrecipe']);
            $(this).prop('selected',true);
          }
        });
        if(!old_parent || old_parent != obj['parentrecipe']) $mod.find('#id_parent').trigger("chosen:updated");

        if(idarr[0] == "Rid") $mod.find('input[name=new_resource_type]').attr('name','edit_resource_type');
        if(idarr[0] == "Sid") $mod.find('input[name=new_skill_type]').attr('name','edit_skill_type');
        $mod.find('#id_edid').attr('value', ide);


        if( tid == "exchange_type" ) {
          //alert(obj);
          $mod.find('#id_parent_type option').each(function(){
            if($(this).prop('selected')) old_et = $(this).val();
            $(this).prop('selected', false);
            if($(this).val() == obj['parent']){
              $(this).prop('selected', true); //alert('Hau!:'+$(this).val());
            }
          });
          if(!old_et || old_et != obj['parent']) $mod.find('#id_parent_type').trigger("chosen:updated");
        }

        $mod.find('.facet-box').remove();
        if(typeof(obj['n_desc'] !== 'undefined') && obj['n_desc'] && obj['n_desc']*1 > 0){
          $mod.find('.form-group').last().after('<div class="form-group facet-box"><label class="control-label">Create a new FacetValue named "'+name+'" under "'+cleantypename($mod.find('#id_resource_type option:selected').text()).trim()+'"?</label> &nbsp; <input id="id_facetvalue" name="facetvalue" type="checkbox"></div>');
        }
        if(typeof(obj['fv'] !== 'undefined') && obj['fv']){
          $mod.find('.modal-footer').first().prepend('<span class="facet-box">'+obj['fv']+'</span> &nbsp; ');
        }
      } else {
        alert('No modal? '+$mod);
      }
    }

    $('#edit_rt_but').click(function(){
        rebuild_modal('resource_type');
    });
    $('#edit_st_but').click(function(){
        rebuild_modal('skill_type');
    });
    $('.edit_exchange_type').click(function(){
        rebuild_modal('exchange_type');
    });
    //alert($('#edit_et_but').length);

    function reset_modal(tid){
        $('.facet-box').remove();
        if( tid == "resource_type" && $('input[name=edit_resource_type]').length) {
          var $mod = $('#addResourceTypeModal');
        } else if( tid == "skill_type" && $('input[name=edit_skill_type]').length) {
          var $mod = $('#addSkillTypeModal');
        }
        if(typeof $mod == 'undefined') return;
        $mod.find('#name_action').text("Add new");
        $mod.find('#id_name').val('');
        $mod.find('#id_description').val('');
        $mod.find('#id_substitutable').val(false).prop('checked', false);
        $mod.find('#id_price_per_unit').val('');
        $mod.find('#id_url').val('');
        $mod.find('#id_photo_url').val('');
        $mod.find('#id_verb').val('');
        $mod.find('#id_gerund').val('');
        //$mod.find('option').removeAttr('selected');

        if( tid == "resource_type" ) {
          var sel_rt = $mod.find('#id_resource_type').find('option:selected').first().attr('value');
          if(old_rt){
            $mod.find('#id_resource_type').find('option').prop('selected', false);
            $mod.find('#id_resource_type').find('option[value='+old_rt+']').prop('selected', true);
          } else if( $('#id_resource_type').find('option:selected').length ) {
            var pid = $('#id_resource_type').first().find('option:selected').attr('value');
            //alert('sels:'+$('#id_resource_type').first().find('option:selected').length+' ('+$('#id_resource_type').first().find('option:selected').attr('value')+') '+$('#id_resource_type').first().find('option:selected').text()+' clas:'+$('#id_resource_type').first().attr('class'));
            $mod.find('#id_resource_type').find('option').prop('selected', false);
            $mod.find('#id_resource_type').find("option[value='"+pid+"']").prop('selected', true);
          } else {
            $mod.find('#id_resource_type').find('option').prop('selected', false);
            $mod.find('#id_resource_type').find("option[value='']").prop('selected', true);
          }
          var new_rt = $mod.find('#id_resource_type').first().find('option:selected').first().attr('value');
        }

        if( tid == "skill_type" ) {
          var sel_rt = $mod.find('#id_parent_type').find('option:selected').first().attr('value');
          if(old_rt){
            $mod.find('#id_parent_type').find('option').prop('selected', false);
            $mod.find('#id_parent_type').find('option[value='+old_rt+']').prop('selected', true);
          } else if( $('#id_skill_type').find('option:selected').length ) {
            var pid = $('#id_skill_type').first().find('option:selected').attr('value');
            //alert('pid: '+pid+' sels:'+$('#id_skill_type').first().find('option:selected').length+' ('+$('#id_skill_type').first().find('option:selected').attr('value')+') '+$('#id_skill_type').first().find('option:selected').text()+' clas:'+$('#id_skill_type').first().attr('class'));
            $mod.find('#id_parent_type').find('option').prop('selected', false);
            $mod.find('#id_parent_type').find("option[value='"+pid+"']").prop('selected', true);
            alert('pid:'+pid+' opt:'+$mod.find('#id_parent_type').find("option[value='"+pid+"']").html());
          } else {
            $mod.find('#id_parent_type').find('option').prop('selected', false);
            $mod.find('#id_parent_type').find("option[value='']").prop('selected', true);
          }
          var new_rt = $mod.find('#id_parent_type').first().find('option:selected').first().attr('value');
        }

        var sel_agent = $mod.find('#id_context_agent').find('option:selected').first().attr('value');
        if(old_agent){
          $mod.find('#id_context_agent').find('option').prop('selected', false);
          $mod.find('#id_context_agent').find('option[value='+old_agent+']').prop('selected', true);
        } else { // context agent can't be empty
          //$mod.find('#id_context_agent').find('option').prop('selected', false);
          //$mod.find('#id_context_agent').find("option[value='']").prop('selected', true);
        }
        var new_agent = $mod.find('#id_context_agent').find('option:selected').first().attr('value');

        $mod.find('#id_unit_type_chosen').find('.search-choice-close').first().click();
        var sel_unit = $mod.find('#id_unit_type').find('option:selected').first().attr('value');
        if(old_unit){
          $mod.find('#id_unit_type').find('option').prop('selected', false);
          $mod.find('#id_unit_type').find('option[value='+old_unit+']').prop('selected', true);
        } else {
          $mod.find('#id_unit_type').find('option').prop('selected', false);
          $mod.find('#id_unit_type').find("option[value='']").prop('selected', true);
        }
        var new_unit = $mod.find('#id_unit_type').find('option:selected').first().attr('value');

        $mod.find('#id_related_type_chosen').find('.search-choice-close').first().click();
        var sel_related = $mod.find('#id_related_type').find('option:selected').first().attr('value');
        if(old_related){
          $mod.find('#id_related_type').find('option[value='+old_related+']').prop('selected', true);
        } else {
          $mod.find('#id_related_type').find("option[value='']").prop('selected', true);
        }
        var new_related = $mod.find('#id_related_type').find('option:selected').first().attr('value');

        if( tid == "resource_type" ) {
          $mod.find('#id_parent_chosen').find('.search-choice-close').first().click();
          var sel_parent = $mod.find('#id_parent').find('option:selected').first().attr('value');
          if(old_parent){
            $mod.find('#id_parent').find('option[value='+old_parent+']').prop('selected', true);
          } else {
            $mod.find('#id_parent').find("option[value='']").prop('selected', true);
          }
          var new_parent = $mod.find('#id_parent').find('option:selected').first().attr('value');
        }


        if(sel_rt != new_rt){
          if( tid == "resource_type" ) {
            $mod.find('#id_resource_type').trigger("chosen:updated");
            if( new_rt != '' && !$mod.find('#id_resource_type_chosen').find('li.result-selected').length ) {
              //alert('Error (js bug): the parent resource type is not displayed (but is selected). Please reselect: '+$('#id_resource_type').find('option:selected').text()+' ('+new_rt+') sel:'+sel_rt+' new:'+new_rt);
              $mod.find('#id_resource_type').trigger("chosen:updated");
            }
          }
          if( tid == "skill_type" ) {
            $mod.find('#id_parent_type').trigger("chosen:updated");
            if( new_rt != '' && !$mod.find('#id_parent_type_chosen').find('li.result-selected').length ) {
              //alert('Error (js bug): the parent skill type is not displayed (but is selected). Please reselect: '+$('#id_skill_type').find('option:selected').text()+' ('+new_rt+') sel:'+sel_rt+' new:'+new_rt);
              $mod.find('#id_parent_type').trigger("chosen:updated");
            }
          }
        }
        if(sel_agent != new_agent){ //alert('diff agent sel:'+sel_agent+' new:'+new_agent);
          $mod.find('#id_context_agent').trigger("chosen:updated");
          if( new_agent != '' && !$mod.find('#id_context_agent_chosen').find('li.result-selected').length ) {
            alert('Error (js bug): the actual context agent is not displayed (but is selected). Please reselect: '+new_agent);
            //$mod.find('#id_context_agent').trigger("chosen:updated");
          }
        }
        if(sel_unit != new_unit){
          $mod.find('#id_unit_type').trigger("chosen:updated");
          if( new_unit != '' && !$mod.find('#id_unit_type_chosen').find('li.result-selected').length ) {
            alert('Error (js bug): the actual unit type is not displayed (but is selected). Please reselect: '+new_unit);
          }
        }
        if(sel_related != new_related){
          $mod.find('#id_related_type').trigger("chosen:updated");
          if( new_related != '' && !$mod.find('#id_related_type_chosen').find('li.result-selected').length ) {
            alert('Error (js bug): the actual related type is not displayed (but is selected). Please reselect: '+new_related);
          }
        }
        if(sel_parent != new_parent){
          $mod.find('#id_parent').trigger("chosen:updated");
          if( new_parent != '' && !$mod.find('#id_parent_chosen').find('li.result-selected').length ) {
            alert('Error (js bug): the actual type for inheriting a recipe is not displayed (but is selected). Please reselect: '+new_parent);
          }
        }

        if( tid == "resource_type" ) $mod.find('input[name=edit_resource_type]').attr('name','new_resource_type');
        if( tid == "skill_type" ) $mod.find('input[name=edit_skill_type]').attr('name','new_skill_type');
        $mod.find('#id_edid').attr('value','');
        //alert('reset tid:'+tid+' sel_rt:'+sel_rt+' new_rt:'+new_rt+' old_rt:'+old_rt);
        //alert('reset tid:'+tid+' sel_agent:'+sel_agent+' new_agent:'+new_agent+' old_agent:'+old_agent);
    }

    $('a.btn_resource_type').click(function(){
        reset_modal("resource_type");
    });
    $('a.btn_skill_type').click(function(){
        reset_modal("skill_type");
    });


    //   T R E E S

    var ObjTree = {
      checkbox: true,
      selectMode: 1, // 1:single, 2:multi, 3:multi-hier
      icon: false,
      dblclick: function(event, data) {
        data.node.toggleSelected();
        //update_tree(data);
      },
      keydown: function(event, data) {
        if( event.which === 32 ) {
          data.node.toggleSelected();
          //update_tree(data);
          return false;
        }
      },
      select: function(event, data){
        var s = data.tree.getSelectedNodes();
        if( data.node.isSelected() && !data.node.isActive() ){
          //data.node.setFocus();
          data.node.setActive();
        }
        update_tree(data);
      },
      beforeSelect: function(event, data){
        //update_tree(data);
      },
      deactivate: function(event, data) {
        //update_tree(data);
      },
      click: function(event, data){
        //var out = 'OB - ';
        //for(var i in data){
        //  out += i+': '+data[i]+', ';
        //};
        //alert(data.targetType);
        var nod = data.tree.getActiveNode();
        if(nod && nod != data.node) nod.setActive(false);

        if(data.targetType == 'expander' || data.targetType == 'checkbox'){

        } else {
          data.node.toggleSelected();//setSelected(true);
          if(data.node.isSelected()){
            data.node.setFocus();
            data.node.setActive();
          } else {
            data.node.setActive(false);
            data.node.setFocus(false);
          }
          return false;
        }
        //update_tree(data);
      },
      beforeExpand: function(event, data) {
        if(data.node.isExpanded() && !data.tree.hasFocus()){ //node.isActive()){
          //return false;
        }
        //logEvent(event, data, "flag=" + flag);
      },

    };

    // Deep copy
    var MultiObjTree = jQuery.extend(true, {}, ObjTree);
    MultiObjTree['selectMode'] = 3;

    $('.exchange_type_tree').fancytree( ObjTree );
    $('.resource_type_tree, .skill_type_tree').fancytree( ObjTree );//MultiObjTree );

    $('.exchange_type_tree').find('.fancytree-node > .fancytree-title > em').each(function(){
      //$(this).parent().parent().find('.fancytree-checkbox').hide();
    });

    function update_tree(data){

      var tid = data.tree.$div.attr('class').split(' ')[0];
      var tarr = tid.split('_');
      tid = tarr[0]+'_'+tarr[1];

      var ide = tarr[0].split('')[0].toUpperCase()+'id';

      var $tab = data.tree.$div.parent().parent();

      //var out = 'OB - ';
      //for(var i in tid){
      //  out += i+': '+tid[i]+', ';
      //};

      if( tid == "exchange_type" || tid == "resource_type" ){ //$tab.attr('id') == tid ){ // only the exchange type matches
        $tab = $('#new_exchange');
        //ide = 'Eid';
        //tid = 'exchange_type';
      }

      var snd = data.tree.getSelectedNodes();
      //alert('UPDATE tree tid:'+tid+' $tab:'+$tab.attr('id')+' ide:'+ide+' snd:'+snd);

      if(snd.length > 0 && $('span.edit#'+snd[0].key).length){
        if(ide == "Rid") $('li.edit_resource_type').show();
        if(ide == "Sid") $('li.edit_skill_type').show();
        if(ide == "Eid") $('li.edit_exchange_type').show();
        //rebuild_modal(tid, snd[0].key);
      } else {
        $('li.edit_resource_type').hide();
        $('li.edit_skill_type').hide();
        $('li.edit_exchange_type').hide();
        //reset_modal(tid);
      }

      if(snd.length > 0){  //  S E L E C T E D   I N   T R E E

        if(data.tree.hasFocus() && $tab.find('#id_'+tid+'_chosen').find('li.search-choice').length == 0){  // TREE HAS FOCUS

          if(snd[0].key != data.node.key || snd.length > 1){
            alert('EIN? snd[0]:'+snd[0].key+' node:'+data.node.key);
          };
          var karr = data.node.key.split('_');
          if(karr[0] == ide){

            //$('#id_'+tid+'_chosen').find('li.result-selected').removeClass('result-selected').addClass('active-result');
            $('.id_'+tid).find('option').prop('selected', false);
            $('.id_'+tid).find('option[value=""]').prop('selected',true);
            //$(".id_"+tid).trigger("chosen:updated");

            $('.id_'+tid).find('option').each(function(){
              $(this).prop('selected', false); //alert(karr[1]);
              if( $(this).attr('value') == karr[1] ){
                $(this).prop('selected', true);
              };
            });
            //$(".id_"+tid).trigger("chosen:updated");

            //alert(opts.length);
            if( tid == "exchange_type" ){
                if(!$.isEmptyObject(data.node.data)){ // when an exchange type is related a resource_type
                  var rel = data.node.data.related;
                  var rar = rel.split('_');
                  if( rar[0] == 'Rid' ) {
                    var rtree = $('#resource_type_tree').first();//resource_skill').find('#'+rel);
                    rtree.fancytree("getTree").activateKey('Rid_'+rar[1]);
                    var nod = rtree.fancytree("getTree").getActiveNode();
                    nod.setSelected(true);
                    nod.setFocus(false);
                    rtree.fancytree("getRootNode").visit(function(node){
                      if( node.isExpanded() && !nod.isDescendantOf(node) ) {
                        node.setExpanded(false);
                      }
                    });
                    rtree.fancytree("getTree").setFocus(false);
                  } else if( rar[0] == 'Sid' ) {
                    var rtree = $('#skill_type_tree').first();
                    rtree.fancytree("getTree").activateKey('Sid_'+rar[1]);
                    var nod = rtree.fancytree("getTree").getActiveNode();
                    nod.setSelected(true);
                    nod.setFocus(false);
                    rtree.fancytree("getRootNode").visit(function(node){
                      if( node.isExpanded() && !nod.isDescendantOf(node) ) {
                        node.setExpanded(false);
                      }
                    });
                    rtree.fancytree("getTree").setFocus(false);
                  } else {
                    alert('Related? rel:'+rel);
                  }
                  //alert('rel: '+rel+' rtree:'+rtree.length);
                } else {
                  var rtree = $('#resource_type_tree').first();
                  var node = rtree.fancytree("getTree").getActiveNode();
                  if(node && node.isSelected()){
                    node.setSelected(false);
                    node.setActive(false);
                    node.setFocus(false);
                  }
                  rtree.fancytree("getTree").setFocus(false);
                }
            }

          } else {
            alert('KARR: '+karr[0]);
          }
          //alert('UpdateTree Put / tid:'+tid+' xid:'+karr[0]+' id:'+karr[1]+' N:'+$('.id_'+tid).length+' SCH:'+$('#id_'+tid+'_chosen').find('li.search-choice').length );//nodo.key);

          $(".id_"+tid).each(function(){
            $(this).trigger("chosen:updated");
          });
          //$("#addResourceTypeModal .id_"+tid).trigger("chosen:updated");

          if(!$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length && tid){

            //  E R R O R   the choice is not present!
            alert('js error!');

            var karr = data.node.key.split('_');
            if(karr[0] == ide){
              $('.id_'+tid).find('option').each(function(){
                $(this).removeAttr('selected'); //alert(karr[1]);
                if( $(this).attr('value') == karr[1] ){
                  $(this).prop('selected',true);
                };
              });
              $(".id_"+tid).trigger("chosen:updated");
            }
            //$("#id_"+tid).trigger("chosen:updated");
            var ind = $tab.find('.id_'+tid).find('option[selected]').index();


            setTimeout(function(){

              //$tab.find(".id_"+tid).trigger("chosen:updated");

              if(!$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length){ // !$tab.find('.id_'+tid).find('option[selected]').length){

                alert("Sorry, there's still a javascript bug here. The choice is not seen in the search box the second time it is selected in the tree (but it's selected, internally)... better deselect and select again.");// \n (tid:"+tid+' node:'+data.node.key+' sCH:'+$('#id_'+tid+'_chosen').find('li.search-choice').length+' ('+$('#id_'+tid+'_chosen').find('li.search-choice').first().text()+') rCH:'+$('#id_'+tid+'_chosen').find('li.result-selected').length+' ('+$('#id_'+tid+'_chosen').find('li.result-selected').first().text()+') oCH:'+$('#id_'+tid).find('option[selected]').length+' ('+$('#id_'+tid).find('option[selected]').first().text()+'))');

                $(".id_"+tid).each(function(){
                  //$(this).trigger("chosen:updated");
                });
              };
            }, 500);

          } // end ERROR

          //$("#id_"+tid).trigger("chosen:updated");
          //$("#id_"+tid).trigger("chosen:ready");
          //$("#id_"+tid).trigger("chosen:activate");
          //$("#id_"+tid+'_chosen').find('.search-field input').focus().blur();

          //data.tree.$div.focus();
          //data.tree.setFocus();

        } else { // selecting: either tree has no focus or there's a choice in chosen

          if( !$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length ){ // no choice in chosen, so no focus

            var karr = data.node.key.split('_');
            if(karr[0] == ide){
              $tab.find('.id_'+tid).find('option').each(function(){
                $(this).prop('selected', false); //alert(karr[1]);
                if( $(this).attr('value') == karr[1] ){
                  $(this).prop('selected', true);
                };
              });
              $tab.find(".id_"+tid).trigger("chosen:updated");
            }
            //alert('tree no focus, sCH:'+$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length+' ('+$tab.find('#id_'+tid+'_chosen').find('li.search-choice').first().text()+') oCHs:'+ $tab.find('.id_'+tid).find('option[selected]').length+' tsnd:'+snd.length+' tsnd[0]:'+snd[0].key);


          } else {
            // selecting: there's a choice in chosen and tree has no focus

          }
        }

        if( tid == "exchange_type" ){
          if(!$.isEmptyObject(data.node.data)){
            var rel = data.node.data.related; //$tab.find('li#'+data.node.key).first().attr('related');//data.node.related;
            var rar = rel.split('_');
            var rtree = $('#resource_type_tree').first();
            if( rar[0] == 'Rid' ) {
              rtree.fancytree("getTree").activateKey('Rid_'+rar[1]);
              var nod = rtree.fancytree("getTree").getActiveNode();
              nod.setSelected(true);//toggleSelected();
              //node.setFocus(true);
              nod.setActive(false);
              nod.setFocus(false);
              rtree.fancytree("getRootNode").visit(function(node){
                //node.setExpanded(false);
                // TODO fold other not related branches
                // mptt: get_ancestors(ascending=False, include_self=False)
                //var anc = node.get_ancestors(true);
                if( node.isExpanded() && !nod.isDescendantOf(node) ) {
                  node.setExpanded(false);
                }
              });
              rtree.fancytree("getTree").setFocus(false);
            } else {
              var node = rtree.fancytree("getTree").getActiveNode();
              if(node && node.isSelected()){
                node.setSelected(false);
                node.setActive(false);
                node.setFocus(false);
              }
              rtree.fancytree("getTree").setFocus(false);
            }
            //alert('rel: '+rel+' rtree:'+rtree.length);
          } else {
            var rtree = $('#resource_type_tree').first();
            var node = rtree.fancytree("getTree").getActiveNode();
            if(node && node.isSelected()){
              node.setSelected(false);
              node.setActive(false);
              node.setFocus(false);
            }
            rtree.fancytree("getTree").setFocus(false);
          }
        }

      } else { //  N O   S E L E C T I O N S   I N   T R E E

        if( data.tree.hasFocus() ) { //&& $('#id_'+tid+'_chosen').find('li.search-choice').length > 0 ){

          $tab.find('#id_'+tid+'_chosen').find('li.result-selected').each(function(){
              //$(this).removeClass('result-selected').addClass('active-result');
          });
          var s = $tab.find('.id_'+tid).find('option').each(function(){
              //$(this).removeAttr('selected');
              //if($(this).attr('value') == '') $(this).attr('selected','selected');
          });
          //$("#id_"+tid).trigger("chosen:updated");

          $('.id_'+tid).find('option').each(function(){
              $(this).removeAttr('selected');
              $(this).prop('selected', false);
              if($(this).attr('value') == '') $(this).prop('selected', true);
          });
          $(".id_"+tid).trigger("chosen:updated");

          if($tab.find('#id_'+tid+'_chosen').find('li.search-choice').length > 0){
            alert('UpdateTree: Nothing selected, repair chosen? sCH:'+$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length+' oCH:'+$tab.find('#id_'+tid).find('option:selected').length);
            //var yd = $('#id_'+tid+'_chosen').find('li.result-selected').first().attr('data-option-array-index');
            //$('.id_'+tid).find('option[selected]').removeAttr('selected');
            //$('.id_'+tid).find('option:eq('+yd+')').first().prop('selected',true);

            $tab.find('#id_'+tid+'_chosen').find('li.search-choice').find('a.search-choice-close').click(); // close choices clicking

            //$("#id_"+tid).trigger("chosen:updated");

            if($tab.find('#id_'+tid+'_chosen').find('li.search-choice').length > 0 || $tab.find('.id_'+tid).find('option:selected').length){
              //alert('UpdateTree? / Nothing s:'+s.length+' tid:'+tid+' oCH:'+$tab.find('#id_'+tid).find('option[selected]').length);
              //$('.id_'+tid).find('option[selected]').exclude("[value='']").removeAttr('selected');
              if($tab.find('#id_'+tid+'_chosen').find('li.search-choice').length > 0 || $tab.find('.id_'+tid).find('option:selected').length){
                //alert('UpdateTree?? / Nothing s:'+s.length+' tid:'+tid+' sCH:'+$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length);
              }
            }
          }
          /*$('.id_'+tid).find('option').each(function(){
              $(this).removeAttr('selected');
              if($(this).attr('value') == '') $(this).prop('selected',true);
          });
          $(".id_"+tid).trigger("chosen:activate");*/
          //$("#addResourceTypeModal .id_"+tid).trigger("chosen:updated");
          //$("#id_"+tid).trigger("chosen:updated");
          //$("#id_"+tid+'_chosen').find('.search-field input').focus();
          //data.tree.setFocus();
          //data.tree.$div.focus();

        } else { // tree has no focus

          var yd = $tab.find('#id_'+tid+'_chosen').find('li.result-selected').first().attr('data-option-array-index');
          $tab.find('.id_'+tid).find('option:selected').prop('selected', false);
          $tab.find('.id_'+tid).find('option:eq('+yd+')').first().prop('selected', true);
          //$('#id_'+tid+'_chosen').find('li.result-selected').removeClass('result-selected').addClass('active-result');
          //$('#id_'+tid).find('option[selected]').removeAttr('selected');
          $(".id_"+tid).trigger("chosen:updated");

          if($tab.find('#id_'+tid+'_chosen').find('li.result-selected').length || $tab.find('#id_'+tid+'_chosen').find('li.search-choice').length || $tab.find('#id_'+tid+'_chosen').find('li.result-selected').length){

            //$tab.find('#id_'+tid+'_chosen').find('li.search-choice').find('a.search-choice-close').click();

            alert('tree no focus, no selections? yd:'+yd+' rCH:'+$('#id_'+tid+'_chosen').find('li.result-selected').length+' ('+$('#id_'+tid+'_chosen').find('li.result-selected').first().html()+') sCH:'+$('#id_'+tid+'_chosen').find('li.search-choice').length+' ('+$('#id_'+tid+'_chosen').find('li.search-choice').first().text()+') oCH:'+$('#id_'+tid).find('option[selected]').length+' ('+$('#id_'+tid).find('option[selected]').first().html()+')');
          }
        }

        if(tid == 'exchange_type'){
          $tab.find('#id_resource_type_chosen').find('li.search-choice').find('a.search-choice-close').click();
          $tab.find('#id_resource_type_chosen').blur();
          $tab.find('#id_skill_type_chosen').find('li.search-choice').find('a.search-choice-close').click();
          $tab.find('#id_skill_type_chosen').blur();
          $tab.find('#id_exchange_type_chosen').find('li.search-choice').find('a.search-choice-close').click();
          $tab.find('#id_exchange_type_chosen').blur();
          $('#sh-exchange_type').focus();
        }
      }
      if( $tab.find('#id_'+tid+'_chosen').find('li.search-choice').length ) {
        var htm = $tab.find('#id_'+tid+'_chosen').find('li.search-choice').html();
        $tab.find('#id_'+tid+'_chosen').find('li.search-choice span').html( htm.split( '. ' ).join('') );
      }
      //$("#id_"+tid).trigger("chosen:updated");

    };



    //   D R O P D O W N S

    var ObjChos = {
      //allow_single_deselect: true,
      width: "290px",
      no_results_text: "Oops, nothing found!",
      max_selected_options: 1,
      disable_search_threshold: 6,
    };
    // Deep copy
    var ObjChosMulti = jQuery.extend(true, {}, ObjChos);
    ObjChosMulti['max_selected_options'] = 0;

    function ChosChange($this, params){
      var tid = $this.attr('id');
      var tarr = tid.split('_');
      tid = tarr[1]+'_'+tarr[2];
      var dess = params['deselected'];
      var sels = params['selected'];
      var $tab = $this.parent().parent().parent();
      var tree = $tab.find('#'+tarr[1]+'_'+tarr[2]+'_tree');//.fancytree("getTree");
      var ide = tarr[1].split('')[0].toUpperCase()+'id_';
      var $nav = false;

      if( tid == "exchange_type" ){
        //$tab = $('#'+$('li.ui-tabs-active').attr('aria-controls')).first();
        //tree = $tab.find('#'+$tab.attr('id')+'_tree');
        if( typeof sels != 'undefined' && sels ){
          tree = $('#'+ide+sels).parentsUntil('div').last().parent();
          $tab = tree.parent().parent();
          $nav = $('.ui-tabs .ui-tabs-nav li[aria-controls='+$tab.attr('id')+'] a').click();
        }
        if( typeof dess != 'undefined' && dess ){
          tree = $('#'+ide+dess).parentsUntil('div').last().parent();
          $tab = tree.parent().parent();
          //$this.blur();
          //tree.fancytree("getTree").setFocus(true);
          //$nav = $('.ui-tabs .ui-tabs-nav li[aria-controls='+$tab.attr('id')+'] a');//.click();
        }
      } else if( !tree.length ){
        if( $tab.attr('class') == 'modal-body' ){ // in the edit of exchange types
          var name = $tab.find('#id_name').val()
          var old = $tab.find('#id_'+tid).find('option:selected').text().trim().split('. ').join('');
          var narr = name.split(' ');
          if( tid == 'resource_type' ) {
            if(dess){
              alert('Chosen Change / modal select? $tab:'+$tab.attr('class')+' dess:'+dess+' sels:'+sels+' tid:'+tid);
            }
            if(sels){
              var nou = $tab.find('#id_'+tid).find('option[value='+sels+']').text().split('. ').join('').trim();
              $tab.find('#id_name').val(narr.slice(0, 1)+' '+nou)
            }
          }
        } //else {
          //alert('Chosen Change / modal select? $tab:'+$tab.attr('class')+' dess:'+dess+' sels:'+sels+' tid:'+tid+' name:'+narr.slice(0,-1)+' old:'+old);
        //}
      };
      //alert('Chosen Change / tab:'+$tab.attr('class')+' tid:'+tid+' sel:'+sels+' des:'+dess+' ('+$('#'+ide+dess).length+') tree:'+tree.attr('id')+' ('+tree.length+') ide:'+ide+' nav:'+$nav.length+' tarr:'+tarr.join('_')+' edit:'+$('span.edit#'+ide+sels).length);

      //tree.fancytree("getTree").setFocus(false);

      if( $tab.find('#id_'+tid+'_chosen').find('li.search-choice').length && typeof sels == 'undefined') {
        $tab.find('#id_'+tid+'_chosen').find('li.search-field').hide()
      } else {
        $tab.find('#id_'+tid+'_chosen').find('li.search-field').show()
      }

      //if(!tree.fancytree("getTree").hasFocus()){
      if(typeof dess != 'undefined' && dess){     //   D E S S E L E C T

        $tab.find('#id_'+tid+'_chosen').find('li.search-field').show();

        $('#id_'+tid+'_chosen').find('li.result-selected').removeClass('result-selected').addClass('active-result');
        $('.id_'+tid).find('option:selected').prop('selected', false);
        $('.id_'+tid).find('option[value=""]').prop('selected', true);

        if(!tree.length){// || ide == 'Eid_'){
          alert('NO TREE! dess:'+dess+' tab:'+$tab.attr('id')+' tid:'+tid+' ide:'+ide+' sel:'+$tab.find('#id_'+tid).find('option:selected').text()+' tree:'+tree.length);

          if( $tab.find('#id_'+tid).find('option:selected').length && !$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length ) {
            alert('NO TREE: repair select... dess:'+dess+' tab:'+$tab.attr('id')+' tid:'+tid+' ide:'+ide+' sel:'+$tab.find('#id_'+tid).find('option:selected').text()+' tree:'+tree.length);
            $tab.find('#id_'+tid).find('option[value='+dess+']').prop('selected', false);
          }
        }

        if(tree.length && !tree.fancytree("getTree").hasFocus() && tree.parent('div:visible').length){ // tree has no focus
          if(typeof dess == 'string'){
            tree.fancytree("getTree").activateKey(ide+dess);
            var nod = tree.fancytree("getTree").getActiveNode();
            nod.setSelected(false);//toggleSelected();
            nod.setFocus(false);
            nod.setActive(false);
            tree.fancytree("getRootNode").visit(function(node){
              if( node.isExpanded() && !tree.fancytree("getTree").getSelectedNodes().length ) { //!nod.isDescendantOf(node) ) {
                node.setExpanded(false, {noAnimation: false, noEvents: false}); //alert('close:'+node.title);
              }
              //return 'skip';
            });
            tree.fancytree("getTree").setFocus(false);
            //$('input[name="new-exchange"]').focus();
            //$this.find('li.result-selected').removeClass('result-selected').addClass('active-result');

            //alert('Chosen Change DESS '+dess+' this:'+$this);// / ide: '+tree.find('#'+ide+dess).attr('id')+' dess:'+dess+' tid:'+tid);//+' / tree:'+tree.html())
          } else {
            for(var des in dess){
              alert('d:'+des+' dess:'+dess[des]);
            }
          }
        } else if(tree.length) { // tree has focus

          //$('#id_'+tid+'_chosen').find('li.search-choice').find('.search-choice-close').click();

          //if( $tab.find('#id_'+tid+'_chosen').find('li.search-choice').length || $tab.find('#id_'+tid+'_chosen').find('li.result-selected').length || $tab.find('#id_'+tid).find('option[selected]').length ) {

              $('#id_'+tid+'_chosen').find('li.result-selected').each(function(){
                  $(this).removeClass('result-selected').addClass('active-result');
              });
              $('.id_'+tid).find('option').each(function(){
                  $(this).prop('selected', false);
                  if($(this).attr('value') == '') $(this).prop('selected', true);
              });

              tree.fancytree("getTree").activateKey(ide+dess);
              var node = tree.fancytree("getTree").getActiveNode();
              node.setSelected(false);//toggleSelected();
              node.setFocus(false);
              node.setActive(false);
              //tree.fancytree("getRootNode").visit(function(node){
                //node.setExpanded(false);
              //});
              tree.fancytree("getTree").setFocus(false);
              //$this.blur().mouseout().parent().find('span').first().focus().mousedown().mouseup().click();
              //$this.blur().mouseout().next().next().mouseover().focus().mousedown().mouseup().click();

              //alert('CH DESS tree has focus this:'+$this.parent().find('span').first().html()+' (node:'+node.key+'), dess:'+dess+' tid:'+tid+' sCH:'+$('#id_'+tid+'_chosen').find('li.search-choice').length+' ('+$('#id_'+tid+'_chosen').find('li.search-choice').first().text()+') rCH:'+$('#id_'+tid+'_chosen').find('li.result-selected').length+' ('+$('#id_'+tid+'_chosen').find('li.result-selected').first().html()+') oCH:'+$('#id_'+tid).find('option[selected]').length+' ('+$('#id_'+tid).find('option[selected]').first().html()+')');
          //}
        } else {
            alert('CH DESS there is no tree! tab:'+$tab.attr('id')+', dess:'+dess+' tid:'+tid+' sCH:'+$tab.find('#id_'+tid+'_chosen').find('li.search-choice').length+' ('+$tab.find('#id_'+tid+'_chosen').find('li.search-choice').first().text()+') rCH:'+$tab.find('#id_'+tid+'_chosen').find('li.result-selected').length+' ('+$tab.find('#id_'+tid+'_chosen').find('li.result-selected').first().html()+') oCH:'+$tab.find('#id_'+tid).find('option:selected').length+' ('+$tab.find('#id_'+tid).find('option:selected').first().html()+')');
        }

      }; // end DESS

      if(typeof sels != 'undefined' && sels){      //     S E L E C T I O N S

        if(!tree.length){ // || ide == 'Eid_'){

          //alert('Chosen Change / modal select? $tab:'+$tab.attr('id'));
          $tab.find('#id_'+tid).find('option:selected').prop('selected', false);
          $tab.find('#id_'+tid).find('option[value='+sels+']').prop('selected', true);

          if( !$tab.find('#id_'+tid).find('option:selected').length && $tab.find('#id_'+tid+'_chosen').find('li.search-choice').length ) {
            alert('NO TREE: repair sels:'+sels+' tab:'+$tab.attr('id')+' tid:'+tid+' force select:'+$tab.find('#id_'+tid).find('option:selected').length);
            $tab.find('#id_'+tid).find('option[value='+sels+']').prop('selected',true);

          }

        }

        if(tree.length && !tree.fancytree("getTree").hasFocus()){
          if(typeof sels == 'string' && sels.length){
            var sel = tree.fancytree("getTree").getSelectedNodes();
            var act = tree.fancytree("getTree").getActiveNode();
            var id = '';
            if(act){
              id = act.key.split('_')[1];
              if( act.key != sel[0].key ) {
                alert('act: '+typeof(act)+': '+act.key+' == sel[0]:'+sel[0].key+' OBs:'+$this.chosen.current_selectedIndex);
              }
            }

            $('#id_'+tid+'_chosen').find('li.result-selected').each(function(){
                $(this).removeClass('result-selected').addClass('active-result');
            });

            if(typeof sel[0] != 'undefined') sel[0].setSelected(false);
            tree.fancytree("getTree").activateKey(ide+sels);
            var node = tree.fancytree("getTree").getActiveNode();
            if(node){
              node.setSelected(); //toggleSelected();
              node.setFocus();
              node.setActive();
              node.setFocus(false);
            }
            tree.fancytree("getTree").setFocus(false);

            $('.id_'+tid).find('option').each(function(){
                $(this).prop('selected', false);
                if($(this).attr('value') == sels) $(this).prop('selected', true);
            });


          } else {
            for(var sel in sels){
              alert('s:'+sel+' sel:'+sels[sel]);
            }
          }
        } else if(tree.length) { // tree has focus
          $tab.find('.id_'+tid).find('option').each(function(){
            //$(this).removeAttr('selected');
            //if($(this).attr('value') == sels) $(this).attr('selected','selected');
          });
          $tab.find('#id_'+tid+'_chosen').find('li.result-selected').each(function(){
            //$(this).removeClass('result-selected').addClass('active-result');
          });
          alert('CH SELS tree has focus. tid:'+tid);
        }
      }

      //var out = 'PARAMS - ';
      //for(var i in params){
      //  out += i+': '+params[i]+', ';
      //};
      //alert(out);//node.selector+' '+node.key);
      //if(str[0]) alert($(str[0]).attr('id')+' :: '+str.length);
      //$this.next().focus();//blur();
      //tree.fancytree("getTree").setFocus(true);
      //tree.focus();

      $("#addResourceTypeModal .id_"+tid).trigger("chosen:updated");
      $("#addSkillTypeModal .id_"+tid).trigger("chosen:updated");

    };


    //   A S S I G N   C H O S E N

    $(".chzn-select").each(function(){
      $(this).chosen( ObjChos ).change( function(evt, params){
        ChosChange( $(this), params );
      }).ready( function(evt, params){
          //alert('Chosen READY: params:'+params+' this:'+$(this).text());//+params['chosen']);
      });
    });
    $(".chzn-select-multi").each(function(){
      $(this).chosen( ObjChosMulti ).change( function(evt, params){
        ChosChange( $(this), params );
      }).ready( function(evt, params){
          //alert('Chosen READY: params:'+params+' this:'+$(this).text());//+params['chosen']);
      });
    });

    $(".chzn-select-single").chosen();



    //   U P D A T E   S E L E C T I O N S   O N L O A D

    $('li.search-choice a').each(function(){
      var chosid = $(this).parents('.chosen-container').attr('id');
      var selid = chosid.split('_chosen').join('');
      var indx = $(this).attr('data-option-array-index');
      var $opt = $('#'+selid).find('option:eq('+indx+')');
      //var tid = selid.split('_')[1].split('')[0].toUpperCase();
      //var ide = tid+'id_'+$opt.val();

      ChosChange($("#"+selid),{'selected':$opt.val()});

      //alert('update:'+$(this).attr('data-option-array-index')+' ide:'+ide+' val:'+$opt.val()+' - '+$opt.text()+' sel:'+$("#"+selid).attr('id'));
      //$(this).find('a.search-choice-close').click(); // clean selections!
    });

});
