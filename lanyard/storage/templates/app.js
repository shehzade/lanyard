let currentTypeFilter = 'all';
let activeFeatFilters = new Set();

function renderCards(items) {
    const grid = document.getElementById('findingsGrid');
    if (!items.length) {
        grid.innerHTML = '<div style="grid-column: 1 / -1; text-align: center; padding: 4rem; color: var(--text-muted); font-family: var(--font-mono);">No badge findings match the current filter criteria.</div>';
        return;
    }

    grid.innerHTML = items.map(item => {
        const cropName = item.crop_path ? item.crop_path.split('/').pop() : '';
        const origName = item.original_path ? item.original_path.split('/').pop() : '';
        const cropSrc = cropName ? `cropped/${cropName}` : (item.image_url || '');
        const origSrc = origName ? `originals/${origName}` : (item.image_url || '');

        const cr80Name = item.template_path ? item.template_path.split('/').pop() : '';
        const cr80Src = cr80Name ? `cr80/${cr80Name}` : '';

        const conf = Math.round((item.confidence || 0) * 100);
        const bType = (item.badge_type || 'badge').toLowerCase();
        const typeClass = bType.includes('visitor') ? 'visitor' : (bType.includes('access') ? 'access' : '');
        
        const features = item.security_features || [];
        const featureChips = features.length 
            ? features.map(f => {
                const fLow = f.toLowerCase();
                let cls = 'feat-chip';
                if (fLow.includes('rfid') || fLow.includes('chip') || fLow.includes('nfc')) cls += ' rfid';
                if (fLow.includes('barcode') || fLow.includes('qr')) cls += ' barcode';
                return `<span class="${cls}">${escapeHtml(f)}</span>`;
            }).join('')
            : '<span style="color: var(--text-muted); font-size: 0.72rem; font-style: italic;">None identified</span>';

        return `
        <div class="card" data-id="${item.id}">
            <div class="card-header">
                <span class="badge-type-tag ${typeClass}">${escapeHtml(item.badge_type || 'BADGE')}</span>
                <div class="conf-indicator">
                    <span class="conf-dot"></span>
                    <span>${conf}% Confidence</span>
                </div>
            </div>
            <div class="image-duo">
                <div class="img-container" onclick="openLightbox('${cropSrc}', 'Badge Crop: ${escapeJs(item.employee_name || item.company_name || 'Badge')}')">
                    <span class="img-tag">Crop</span>
                    <img src="${cropSrc}" alt="Badge Crop" onerror="this.src='${item.image_url || ''}';">
                    <div class="img-inspect-hint">Click to Inspect</div>
                </div>
                <div class="img-container" onclick="openLightbox('${origSrc}', 'Original Context: ${escapeJs(item.employee_name || item.company_name || 'Badge Context')}')">
                    <span class="img-tag">Original</span>
                    <img src="${origSrc}" alt="Original Context" onerror="this.src='${item.image_url || ''}';">
                    <div class="img-inspect-hint">Click to Inspect</div>
                </div>
            </div>
            <div class="card-body">
                <div class="target-header">
                    <div>
                        <div class="target-name">${escapeHtml(item.employee_name || 'Anonymous Employee')}</div>
                        <div class="target-org">${escapeHtml(item.company_name || 'Company Unspecified')}</div>
                    </div>
                </div>
                ${item.department_or_role ? `<div class="target-role">${escapeHtml(item.department_or_role)}</div>` : ''}
                ${item.post_author ? `
                    <div class="author-osint">
                        <span class="author-label">Author</span>
                        <span class="author-val">${escapeHtml(item.post_author)}</span>
                    </div>
                ` : ''}
                <div class="meta-table">
                    <span class="meta-k">Badge ID</span>
                    <span class="meta-v">${escapeHtml(item.id_or_badge_number || 'N/A')}</span>
                    <span class="meta-k">Features</span>
                    <div class="chips-list">${featureChips}</div>
                </div>
                ${item.post_caption ? `
                    <div class="post-caption-box">
                        <div class="post-caption-header">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                            Post Context
                        </div>
                        <div class="post-caption-text">${escapeHtml(item.post_caption)}</div>
                    </div>
                ` : ''}
                ${item.summary ? `<div class="summary-text">${escapeHtml(item.summary)}</div>` : ''}
            </div>
            <div class="card-footer">
                ${item.post_url ? `
                    <a href="${item.post_url}" target="_blank" rel="noopener noreferrer" class="source-link">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
                        Source Post
                    </a>
                ` : '<span></span>'}
                <div style="display: flex; gap: 0.45rem; align-items: center;">
                    ${cr80Src ? `
                        <button class="btn-tmpl" onclick="openLightbox('${cr80Src}', 'CR80 Card: ${escapeJs(item.employee_name || item.company_name || 'Badge')}')" title="Inspect actual badge converted to CR80">
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="16" rx="2"></rect><circle cx="9" cy="10" r="2"></circle><line x1="15" y1="8" x2="17" y2="8"></line><line x1="15" y1="12" x2="17" y2="12"></line></svg>
                            CR80 Card
                        </button>
                        <a href="${cr80Src}" download="${cr80Name}" class="btn-tmpl" title="Download CR80 print card (.png)">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                        </a>
                    ` : ''}
                    <button class="copy-btn" title="Copy metadata" onclick="copyCardData(${item.id})">
                        Copy JSON
                    </button>
                </div>
            </div>
        </div>
        `;
    }).join('');
}

function filterCards() {
    const query = document.getElementById('searchInput').value.toLowerCase().trim();
    
    let filtered = rawFindings.filter(item => {
        if (currentTypeFilter !== 'all') {
            const bType = (item.badge_type || '').toLowerCase();
            if (!bType.includes(currentTypeFilter)) return false;
        }

        if (activeFeatFilters.size > 0) {
            const feats = (item.security_features || []).map(f => f.toLowerCase()).join(' ');
            for (let f of activeFeatFilters) {
                if (!feats.includes(f)) return false;
            }
        }

        if (query) {
            const matchStr = [
                item.employee_name || '',
                item.post_author || '',
                item.company_name || '',
                item.department_or_role || '',
                item.id_or_badge_number || '',
                item.post_caption || '',
                item.summary || '',
                (item.security_features || []).join(' ')
            ].join(' ').toLowerCase();

            if (!matchStr.includes(query)) return false;
        }

        return true;
    });

    const sortMode = document.getElementById('sortSelect').value;
    filtered.sort((a, b) => {
        if (sortMode === 'confidence_desc') return (b.confidence || 0) - (a.confidence || 0);
        if (sortMode === 'confidence_asc') return (a.confidence || 0) - (b.confidence || 0);
        if (sortMode === 'name_asc') return (a.employee_name || 'ZZZ').localeCompare(b.employee_name || 'ZZZ');
        if (sortMode === 'company_asc') return (a.company_name || 'ZZZ').localeCompare(b.company_name || 'ZZZ');
        return 0;
    });

    renderCards(filtered);
}

function setTypeFilter(type) {
    currentTypeFilter = type;
    document.querySelectorAll('.filter-groups .pill[data-type]').forEach(el => {
        el.classList.toggle('active', el.getAttribute('data-type') === type);
    });
    filterCards();
}

function toggleFeatureFilter(feat) {
    const pill = document.querySelector(`.filter-groups .pill[data-feat="${feat}"]`);
    if (activeFeatFilters.has(feat)) {
        activeFeatFilters.delete(feat);
        pill.classList.remove('active');
    } else {
        activeFeatFilters.add(feat);
        pill.classList.add('active');
    }
    filterCards();
}

function sortCards() {
    filterCards();
}

let currentZoom = 1;
let panX = 0;
let panY = 0;
let isPanning = false;
let startX = 0;
let startY = 0;

function updateTransform() {
    const img = document.getElementById('modalImg');
    img.style.transform = `translate(${panX}px, ${panY}px) scale(${currentZoom})`;
}

function openLightbox(src, caption) {
    const img = document.getElementById('modalImg');
    img.src = src;
    document.getElementById('modalCaption').innerText = caption;
    currentZoom = 1;
    panX = 0;
    panY = 0;
    updateTransform();
    document.getElementById('lightboxModal').classList.add('open');
}

function closeLightbox(e) {
    if (e.target.id === 'lightboxModal') {
        closeLightboxDirect();
    }
}

function closeLightboxDirect() {
    document.getElementById('lightboxModal').classList.remove('open');
}

function zoomIn(e) {
    if (e) e.stopPropagation();
    currentZoom = Math.min(currentZoom * 1.35, 5.0);
    updateTransform();
}

function zoomOut(e) {
    if (e) e.stopPropagation();
    currentZoom = Math.max(currentZoom / 1.35, 0.7);
    updateTransform();
}

function resetZoom(e) {
    if (e) e.stopPropagation();
    currentZoom = 1;
    panX = 0;
    panY = 0;
    updateTransform();
}

function handleWheel(e) {
    e.preventDefault();
    if (e.deltaY < 0) {
        currentZoom = Math.min(currentZoom * 1.15, 5.0);
    } else {
        currentZoom = Math.max(currentZoom / 1.15, 0.7);
    }
    updateTransform();
}

function startPan(e) {
    if (e.button !== 0) return;
    isPanning = true;
    startX = e.clientX - panX;
    startY = e.clientY - panY;
    window.addEventListener('mousemove', doPan);
    window.addEventListener('mouseup', stopPan);
}

function doPan(e) {
    if (!isPanning) return;
    panX = e.clientX - startX;
    panY = e.clientY - startY;
    updateTransform();
}

function stopPan() {
    isPanning = false;
    window.removeEventListener('mousemove', doPan);
    window.removeEventListener('mouseup', stopPan);
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightboxDirect();
});

function copyCardData(id) {
    const item = rawFindings.find(f => f.id === id);
    if (item) {
        navigator.clipboard.writeText(JSON.stringify(item, null, 2)).then(() => {
            alert('Badge metadata copied to clipboard as JSON.');
        });
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeJs(str) {
    if (!str) return '';
    return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

filterCards();
