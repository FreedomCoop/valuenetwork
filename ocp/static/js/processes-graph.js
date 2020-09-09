

function viewStatistics() {
	var c = $('<div/>');
	c.append('<b>Projects:</b> ' + _.map( valnet.projects(), function(v) { return v.name; } ).join(',') + '<br/>');
	c.append('<b>Agents:</b> ' + _.map( valnet.agents(), function(v) { return v.name; } ).join(',') + '<br/>');
	c.append('<b>Processes:</b> ' + _.map( valnet.processes(), function(v) { return v.name; } ).join(',') + '<br/>');
	c.append('<b>Resource Types:</b> ' + _.map( valnet.resourceTypes(), function(v) { return v.name; } ).join(',') + '<br/>');
	$('#content').html(c);
}

function viewProjects() {
	var c = $('<div/>');

	function newProjectSummary(pid, p) {
		var s = $('<div/>');
		var projectId = pid.split("-")[1];
		var anchor = '<a href="/accounting/processes-graph/P/' + projectId + '">Open process graph for this project</a>';
		s.append('<h2>' + p.name + ' ' + anchor + '</h2>');
		s.append('Processes:<br/>');
		var proclist = $('<ul/>');
		var procs = valnet.processesInProject(pid);
		_.each(procs, function(pr) {
			proclist.append('<li>' + pr.name + '</li>');
		});
		s.append(proclist);
		return s;
	}

	_.each( valnet.projects(), function(p, pid) {
		c.append(newProjectSummary(pid, p));
	});
    $('#content').html('');
	$('#container').html(c);
}

function viewAgents() {
	var c = $('<div/>');

	function newAgentSummary(aid, a) {
		var s = $('<div/>');
		var agentId = aid.split("-")[1];
		var anchor = '<a href="/accounting/processes-graph/A/' + agentId + '">Open process graph for this agent</a>';
		s.append('<h2>' + a.name + ' ' + anchor + '</h2>');
		s.append('Processes:<br/>');
		var proclist = $('<ul/>');
		var procs = a.processes;
		_.each(procs, function(pr) {
			var P = valnet.processes()[pr];
			proclist.append('<li>' + P.name + '</li>');
		});
		s.append(proclist);
		return s;
	}

	_.each( valnet.agents(), function(a, aid) {
		c.append(newAgentSummary(aid, a));
	});

    $('#content').html('');
	$('#container').html(c);
}

function viewResources() {
	var c = $('<div/>');

	function newResourceSummary(aid, a) {
		var s = $('<div/>');
		s.append('<p><a href="' + a.url + '">' + a.name + '</a></p>');
		//s.append(JSON.stringify(a));
		if (a['photo-url']) {
			s.append('<img src="' + a['photo-url'] + '"/>')
		}
		//s.append('<br/>');
		/*s.append('Processes:<br/>');
		var proclist = $('<ul/>');
		var procs = a.processes;
		_.each(procs, function(pr) {
			var P = valnet.processes()[pr];
			proclist.append('<li>' + P.name + '</li>');
		});
		s.append(proclist);*/
		return s;
	}

	_.each( valnet.resourceTypes(), function(a, aid) {
		c.append(newResourceSummary(aid, a));
	});

    $('#content').html('');
	$('#container').html(c);
}

function viewOrders() {
    var c = $('<div/>');

	function newOrderSummary(pid, o) {
		var s = $('<div/>');
		var orderId = pid.split("-")[1];
		var anchor = '<a href="/accounting/processes-graph/O/' + orderId + '">Open process graph for this order</a>';
		s.append('<h2>' + o.name + ' ' + anchor + '</h2>');
		s.append('Processes:<br/>');
		var proclist = $('<ul/>');
		var procs = o.processes;
		_.each(procs, function(pr) {
			var P = valnet.processes()[pr];
			proclist.append('<li>' + P.name + '</li>');
		});
		s.append(proclist);
		return s;
	}

	_.each( valnet.orders(), function(p, pid) {
		c.append(newOrderSummary(pid, p));
	});
    $('#content').html('');
	$('#container').html(c);
}

$(document).ready(function() {


	load(function() {


		$("#ViewProjects").click(viewProjects);
		$("#ViewStatistics").click(viewStatistics);
		$("#ViewAgents").click(viewAgents);
		$("#ViewResources").click(viewResources);
		$("#ViewOrders").click(viewOrders);
		$("#ViewProcesses").click(viewProcessGraph);

		viewProcessGraph();

        $("#loading").hide("slide", { direction: "left" }, "slow");

	});


}); // end document.ready

        var nodes = [];
        var nodeIndex = {};
        var edges = [];
        var constraints = [];

function assembleNodes(){


        var minDate=-1, maxDate;



        for (var i in valnet.processes()) {
            var N = valnet.processes()[i];
            if (N.start == N.end)
            {
                var start = Date.parse(N.start) - 75;
                var end = Date.parse(N.end) + 75;
            }
            else
            {
                var start = Date.parse(N.start);
                var end = Date.parse(N.end);
            }
            var mid = (start + end)/2.0;
            N.mid = mid;
            if (minDate == -1)
            {
                //minDate = maxDate = mid;
                minDate = start;
                maxDate = end;
            }
            else
            {
                //if (mid < minDate) minDate = mid;
                //if (mid > maxDate) maxDate = mid;
                if (start < minDate) minDate = start;
                if (end > maxDate) maxDate = end;
            }
        }

        var xScale = 1000;
        function getX(date) {
            var x = (maxDate!=minDate) ? xScale * (date - minDate) / (maxDate - minDate) : 0;
            return x;
        }

        //add resource type nodes
        for (var i in valnet.resourceTypes()) {
            var N = valnet.resourceTypes()[i];
            var rx = xScale * Math.random();
            // doesn't make much diff
            var ry = 500 * Math.random();

            var width = 150;
            var height = 100;

            nodes.push( { name: N.name, color: "#bbf", width: width, height: 25, url: N.url } );
            nodeIndex[i] = nodes.length-1;
        }

        //add process nodes
        for (var i in valnet.processes()) {
            var N = valnet.processes()[i];

            var rx = getX(N.mid);
            // doesn't make much diff
            var ry = 100 * Math.random();

            var width = Math.max(150, getX(Date.parse(N.end)) - getX(Date.parse(N.start)));
            var height = 50;

            var dates = N.start + '..' + N.end;
            nodes.push( { name: N.name, dates: dates, color: "#bfb", width: width, height: 40, fixedX: rx, url: N.url, type: N.type } );
            nodeIndex[i] = nodes.length-1;

            for (var j = 0; j < N.next.length; j++) {
                edges.push( { source: nodeIndex[i], target: nodeIndex[N.next[j]] } );
            }
        }

        //add outgoing edges from resource types
        for (var i in valnet.resourceTypes()) {
            var N = valnet.resourceTypes()[i];
            for (var k = 0; k < N.next.length; k++) {
                var nextProcess = N.next[k];
                edges.push( { source: nodeIndex[i], target: nodeIndex[nextProcess] } );
            }
        }

} // end assembleNodes

function viewProcessGraph() {

		$('#container').html('');
		$('#content').html('');

		var maxWidth = $(window).width(), maxHeight = $(window).height();

        var d3cola = cola.d3adaptor()
            .linkDistance(30)
            .size([maxWidth, maxHeight]);

		var svgCanvas = d3.select("#content").append("svg")
			.attr("width", "80%")
			.attr("height", "80%");

		svg = d3.select("#content svg").append('g');

		svg.append("defs").append("marker")
            .attr("id", "arrowhead")
            .attr('viewBox', '0 -5 10 10')
            .attr('refX', 15)
            .attr('markerWidth', 12)
            .attr('markerHeight', 12)
            .attr('orient', 'auto')
          .append('svg:path')
            .attr('d', 'M0,-5L10,0L0,5')
            .attr('fill', '#000');
/*
		var force = d3.layout.force()
            .charge(-120)
			.gravity(.09)
			.linkDistance(30)
			.linkStrength(0.1) //necessary to be < 1.0 to make sure charge (repulsion) is stronger
			.charge(-500)
			.size([maxWidth, maxHeight]);
*/


        assembleNodes();

		 d3cola
            .nodes(nodes)
            .links(edges)
            //.constraints(constraints)
            .symmetricDiffLinkLengths(5)
            .avoidOverlaps(true)
            .start(10,15,2);

	      var drag = d3cola.drag()
    		.on("dragstart", function() {
				oncell = true;
			}).on("dragend", function() {
				oncell = false;
			});

		  var link = svg.selectAll(".link")
			  .data(edges)
			  .enter().append("line")
			  .attr("marker-end", "url(#arrowhead)")
			  .attr("class", "link");

		  var node = svg.selectAll(".node")
			  .data(nodes)
			  .enter().append("g")
			  .attr("class", "node")
			  .attr("type", function(d) {return d.type })
			  .call(d3cola.drag);

	        node.on("dblclick", function(d) {
		        if (d3.event.defaultPrevented) return; // ignore drag
		        window.open(d.url);
	        });

	        node.on("click", function(d) {
                if (d3.event.defaultPrevented) return; // ignore drag
                if (d.fixed)
                {
                    d.fixed=false;
                    d.color=d.oldColor;
                    this.firstChild.style.fill = d.color;
                }
                else
                {
                    d.fixed=true;
                    d.oldColor=d.color;
                    if (d.type == "process")
                    { d.color="#4cfe4c"; }
                    else
                    { d.color="#dda0dd"; }
                    this.firstChild.style.fill = d.color;
                }
            });

  		  node.append("rect")
             .attr("x", function(d) { return -d.width/2; })
             .attr("y", function(d) { return -d.height/2; })
             .attr("width", function(d) { return d.width; } )
             .attr("height", function(d) { return d.height; } )
			 .style("fill", function(d) { return d.color; });


        node.append("text")
            .attr("dx", function(d) { return -d.width/2; })
            .attr("dy", function(d) {
                if (d.dates)
                { return -4 }
                else
                {return 0 }
            })
            .attr("fill", "blue")
            .text(function(d) {return d.name });

        node.append("text")
            .attr("dx", function(d) { return -d.width/2; })
            .attr("dy", function(d) { return "1em" })
            .attr("fill", "black")
            .text(function(d) {return d.dates });

		  d3cola.on("tick", function() {
			node.attr("transform", function(d) {
				if (d.fixedX!=undefined) d.x = d.fixedX;
				return "translate(" + d.x + "," + d.y + ")";
            });

			link.attr("x1", function(d) { return d.source.x + d.source.width/2; })
				.attr("y1", function(d) { return d.source.y; })
				.attr("x2", function(d) { return d.target.x - d.target.width/2; })
				.attr("y2", function(d) { return d.target.y; });

			d3cola.stop();

		  });

		var scale = 1.0;
		var dragging = false;
		var lastPoint = null;
		var startDragPoint = null;
		var tx = 0, ty = -200;
		var oncell = false;

		var cc = $("#content");
		var ss = $("#content svg");
		var ssg = $("#content svg g");

		var ended = false;
	    d3cola.on("end", function() {
			ended = true;
		});

		function updateSVGTransform() {
			ssg.attr('transform', 'translate(' + tx + ',' + ty +') scale('+scale+','+scale+')');
			if (ended) {
				d3cola.start();
				d3cola.tick();
				d3cola.stop();
			}
		}

		ss.mousewheel(function(evt){
			var direction = evt.deltaY;

			if (direction > 0) {
				scale *= 0.9;
			}
			else {
				scale /= 0.9;
			}

			updateSVGTransform();
		});

		cc.mousedown(function(m) {
			if ((m.which==1) && (!oncell)) {
				dragging = true;
				startDragPoint = [m.clientX, m.clientY];
			}
		});

		cc.mouseup(function(m) {
			dragging = false;
			lastPoint = null;
		});

		cc.mousemove(function(m) {
			if (m.which!=1) {
				dragging = false;
				lastPoint = null;
				return;
			}

			if (dragging) {
				if (lastPoint) {
					var dx = m.clientX - lastPoint[0];
					var dy = m.clientY - lastPoint[1];
					tx += dx;
					ty += dy;
					updateSVGTransform();
				}

				lastPoint = [m.clientX, m.clientY];

			}
		});

} // end viewProcessGraph