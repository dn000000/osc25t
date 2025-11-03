// Global variables
let cy = null;
let currentGraphType = 'runtime';
let graphData = null;

// Check if cose-bilkent is available
let coseBilkentAvailable = false;

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Register Cytoscape extensions
    if (typeof cytoscape !== 'undefined' && typeof cytoscapeCoseBilkent !== 'undefined') {
        try {
            cytoscape.use(cytoscapeCoseBilkent);
            coseBilkentAvailable = true;
            console.log('Cytoscape cose-bilkent layout registered successfully');
        } catch (e) {
            console.error('Failed to register cose-bilkent:', e);
            coseBilkentAvailable = false;
        }
    } else {
        console.warn('Cytoscape cose-bilkent not available, will use fallback layout');
        if (typeof cytoscape === 'undefined') {
            console.error('Cytoscape not loaded!');
        }
        if (typeof cytoscapeCoseBilkent === 'undefined') {
            console.error('cytoscapeCoseBilkent not loaded!');
        }
    }
    
    initializeEventListeners();
    loadGraph(currentGraphType);
});

// Get layout configuration based on graph structure and available layouts
function getLayoutConfig(elements) {
    const hasEdges = elements.some(e => e.group === 'edges');
    const nodeCount = elements.filter(e => e.group === 'nodes').length;
    
    console.log(`Selecting layout for ${nodeCount} nodes, hasEdges: ${hasEdges}`);
    
    // If no edges, use grid layout
    if (!hasEdges) {
        console.log('Using grid layout (no edges)');
        return {
            name: 'grid',
            rows: Math.ceil(Math.sqrt(nodeCount)),
            cols: Math.ceil(Math.sqrt(nodeCount)),
            animate: false
        };
    }
    
    // For very large graphs, use circle layout (faster)
    if (nodeCount > 200) {
        console.log('Using circle layout for large graph');
        return {
            name: 'circle',
            animate: false,
            radius: Math.max(200, nodeCount / 2),
            startAngle: 0,
            sweep: 2 * Math.PI
        };
    }
    
    // For medium graphs, use cose layout (built-in, always available)
    console.log('Using cose layout');
    return {
        name: 'cose',
        animate: false,
        nodeDimensionsIncludeLabels: true,
        idealEdgeLength: 100,
        nodeRepulsion: 4500,
        numIter: 1000,
        randomize: false
    };
}

// Initialize all event listeners
function initializeEventListeners() {
    document.getElementById('graph-type').addEventListener('change', function(e) {
        currentGraphType = e.target.value;
        loadGraph(currentGraphType);
    });

    document.getElementById('search-btn').addEventListener('click', searchPackage);
    
    document.getElementById('search-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            searchPackage();
        }
    });

    document.getElementById('clear-search-btn').addEventListener('click', clearSearch);
    document.getElementById('reset-view-btn').addEventListener('click', resetView);
    document.getElementById('fit-graph-btn').addEventListener('click', fitGraph);
    document.getElementById('close-details-btn').addEventListener('click', closeDetails);
}

// Load graph data from API
async function loadGraph(graphType) {
    showLoading(true);
    hideError();
    closeDetails();

    try {
        const response = await fetch(`/api/graph/${graphType}`);
        
        if (!response.ok) {
            throw new Error(`Failed to load graph: ${response.statusText}`);
        }

        graphData = await response.json();
        
        // Check if graph is too large
        const nodeCount = graphData.nodes ? graphData.nodes.length : 0;
        const edgeCount = graphData.edges ? graphData.edges.length : 0;
        const MAX_NODES = 500;
        
        console.log(`Loaded graph: ${nodeCount} nodes, ${edgeCount} edges`);
        
        if (nodeCount === 0) {
            showError('No nodes in graph. The graph may be empty.');
            showLoading(false);
            return;
        }
        
        if (nodeCount > MAX_NODES) {
            showLoading(true, `Rendering large graph (${nodeCount} nodes)...`);
            await new Promise(resolve => setTimeout(resolve, 100)); // Allow UI to update
            
            showError(`Graph is too large (${nodeCount} nodes). Showing first ${MAX_NODES} nodes. Use search to find specific packages.`);
            // Limit nodes
            graphData.nodes = graphData.nodes.slice(0, MAX_NODES);
            // Filter edges to only include nodes we're showing
            const nodeIds = new Set(graphData.nodes.map(n => n.id));
            graphData.edges = graphData.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
        } else if (nodeCount > 100) {
            showLoading(true, `Rendering graph (${nodeCount} nodes)...`);
            await new Promise(resolve => setTimeout(resolve, 100)); // Allow UI to update
        }
        
        try {
            renderGraph(graphData);
            updateStats(graphData);
        } catch (error) {
            console.error('Error rendering graph:', error);
            showError(`Failed to render graph: ${error.message}`);
        }
        showLoading(false);
    } catch (error) {
        console.error('Error loading graph:', error);
        showError(`Failed to load graph data: ${error.message}`);
        showLoading(false);
    }
}

// Render the graph using Cytoscape.js
function renderGraph(data) {
    const container = document.getElementById('graph-container');
    
    // Destroy existing graph if any
    if (cy) {
        cy.destroy();
    }

    // Transform data to Cytoscape format
    const elements = transformDataToCytoscape(data);
    
    console.log(`Rendering graph with ${elements.filter(e => e.group === 'nodes').length} nodes and ${elements.filter(e => e.group === 'edges').length} edges`);

    // Initialize Cytoscape
    cy = cytoscape({
        container: container,
        elements: elements,
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)',
                    'background-color': '#667eea',
                    'color': '#fff',
                    'text-valign': 'center',
                    'text-halign': 'center',
                    'font-size': '12px',
                    'width': '40px',
                    'height': '40px',
                    'border-width': 2,
                    'border-color': '#5568d3',
                    'text-outline-color': '#2d3748',
                    'text-outline-width': 2
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#cbd5e0',
                    'target-arrow-color': '#cbd5e0',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'arrow-scale': 1.5
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'background-color': '#f6ad55',
                    'border-color': '#ed8936',
                    'border-width': 3
                }
            },
            {
                selector: 'node.highlighted',
                style: {
                    'background-color': '#48bb78',
                    'border-color': '#38a169',
                    'border-width': 3
                }
            },
            {
                selector: 'edge.highlighted',
                style: {
                    'line-color': '#48bb78',
                    'target-arrow-color': '#48bb78',
                    'width': 3
                }
            },
            {
                selector: '.dimmed',
                style: {
                    'opacity': 0.3
                }
            },
            {
                selector: '.searched',
                style: {
                    'background-color': '#f56565',
                    'border-color': '#e53e3e',
                    'border-width': 4
                }
            }
        ],
        layout: getLayoutConfig(elements),
        minZoom: 0.1,
        maxZoom: 3,
        wheelSensitivity: 0.2
    });

    // Add click event for nodes
    cy.on('tap', 'node', function(evt) {
        const node = evt.target;
        showPackageDetails(node);
        highlightConnections(node);
    });

    // Add click event for background
    cy.on('tap', function(evt) {
        if (evt.target === cy) {
            clearHighlight();
            closeDetails();
        }
    });
}

// Transform graph data to Cytoscape format
function transformDataToCytoscape(data) {
    const elements = [];

    // Add nodes
    if (data.nodes) {
        console.log(`Transforming ${data.nodes.length} nodes`);
        data.nodes.forEach(node => {
            elements.push({
                group: 'nodes',
                data: {
                    id: node.id,
                    label: node.label || node.id,
                    metadata: node.metadata || {}
                }
            });
        });
    } else {
        console.warn('No nodes in data');
    }

    // Add edges
    if (data.edges) {
        console.log(`Transforming ${data.edges.length} edges`);
        data.edges.forEach((edge, index) => {
            elements.push({
                group: 'edges',
                data: {
                    id: `edge-${index}`,
                    source: edge.source,
                    target: edge.target,
                    type: edge.type || 'dependency'
                }
            });
        });
    } else {
        console.warn('No edges in data');
    }

    console.log(`Total elements: ${elements.length}`);
    return elements;
}

// Show package details panel
function showPackageDetails(node) {
    const data = node.data();
    const metadata = data.metadata || {};
    
    document.getElementById('detail-name').textContent = data.id;
    document.getElementById('detail-version').textContent = metadata.version || 'N/A';
    document.getElementById('detail-arch').textContent = metadata.arch || 'N/A';

    // Get dependencies (outgoing edges)
    const dependencies = node.outgoers('node').map(n => n.id());
    const depList = document.getElementById('dependencies-list');
    depList.innerHTML = '';
    if (dependencies.length > 0) {
        dependencies.forEach(dep => {
            const li = document.createElement('li');
            li.textContent = dep;
            depList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = 'No dependencies';
        li.style.fontStyle = 'italic';
        depList.appendChild(li);
    }

    // Get dependents (incoming edges)
    const dependents = node.incomers('node').map(n => n.id());
    const depntList = document.getElementById('dependents-list');
    depntList.innerHTML = '';
    if (dependents.length > 0) {
        dependents.forEach(dep => {
            const li = document.createElement('li');
            li.textContent = dep;
            depntList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = 'No dependent packages';
        li.style.fontStyle = 'italic';
        depntList.appendChild(li);
    }

    document.getElementById('package-details').style.display = 'block';
}

// Close package details panel
function closeDetails() {
    document.getElementById('package-details').style.display = 'none';
}

// Highlight node connections
function highlightConnections(node) {
    // Clear previous highlights
    clearHighlight();

    // Highlight the selected node
    node.addClass('highlighted');

    // Highlight connected nodes and edges
    const connectedEdges = node.connectedEdges();
    const connectedNodes = node.neighborhood('node');
    
    connectedEdges.addClass('highlighted');
    connectedNodes.addClass('highlighted');

    // Dim other nodes
    cy.nodes().not(node).not(connectedNodes).addClass('dimmed');
    cy.edges().not(connectedEdges).addClass('dimmed');
}

// Clear all highlights
function clearHighlight() {
    if (cy) {
        cy.elements().removeClass('highlighted dimmed searched');
    }
}

// Search for a package
function searchPackage() {
    const searchTerm = document.getElementById('search-input').value.trim().toLowerCase();
    
    if (!searchTerm) {
        return;
    }

    if (!cy) {
        showError('Graph not loaded yet');
        return;
    }

    clearHighlight();

    // Find matching nodes
    const matchingNodes = cy.nodes().filter(node => {
        return node.id().toLowerCase().includes(searchTerm);
    });

    if (matchingNodes.length === 0) {
        showError(`No packages found matching "${searchTerm}"`);
        return;
    }

    // Highlight matching nodes
    matchingNodes.addClass('searched');

    // If only one match, show details and center on it
    if (matchingNodes.length === 1) {
        const node = matchingNodes[0];
        showPackageDetails(node);
        highlightConnections(node);
        cy.animate({
            center: { eles: node },
            zoom: 1.5
        }, {
            duration: 500
        });
    } else {
        // Multiple matches - fit all in view
        cy.animate({
            fit: { eles: matchingNodes, padding: 50 }
        }, {
            duration: 500
        });
        showError(`Found ${matchingNodes.length} packages matching "${searchTerm}"`);
    }
}

// Clear search
function clearSearch() {
    document.getElementById('search-input').value = '';
    clearHighlight();
    closeDetails();
    hideError();
}

// Reset view to initial state
function resetView() {
    if (cy) {
        clearHighlight();
        closeDetails();
        cy.animate({
            fit: { padding: 30 },
            zoom: 1
        }, {
            duration: 500
        });
    }
}

// Fit graph to screen
function fitGraph() {
    if (cy) {
        cy.fit(null, 30);
    }
}

// Update statistics
function updateStats(data) {
    const nodeCount = data.nodes ? data.nodes.length : 0;
    const edgeCount = data.edges ? data.edges.length : 0;
    const cycleCount = data.cycles ? data.cycles.length : 0;

    document.getElementById('stat-packages').textContent = nodeCount;
    document.getElementById('stat-dependencies').textContent = edgeCount;
    document.getElementById('stat-cycles').textContent = cycleCount;
}

// Show loading indicator
function showLoading(show, message = 'Loading graph data...') {
    const loading = document.getElementById('loading');
    const loadingMessage = document.getElementById('loading-message');
    loading.style.display = show ? 'block' : 'none';
    if (loadingMessage) {
        loadingMessage.textContent = message;
    }
}

// Show error message
function showError(message) {
    const errorDiv = document.getElementById('error');
    const errorMessage = document.getElementById('error-message');
    errorMessage.textContent = message;
    errorDiv.style.display = 'block';
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        hideError();
    }, 5000);
}

// Hide error message
function hideError() {
    document.getElementById('error').style.display = 'none';
}
