/* PINCABOS_EXPLORER_TABLE_TEST_CENTER_V1 */
(function(){
  "use strict";

  const root=document.getElementById("pco-dashboard-batch-controls");
  if(!root || document.getElementById("pco-dashboard-table-test-row")) return;

  const style=document.createElement("style");
  style.textContent=`
    #pco-dashboard-table-test-row.is-go .pco-batch-title i{background:#45e58b}
    #pco-dashboard-table-test-row.is-warning .pco-batch-title i{background:#ffb300}
    #pco-dashboard-table-test-row.is-problem .pco-batch-title i{background:#ff5d6c}
    #pco-dashboard-table-test-row[hidden]{display:none!important}
  `;
  document.head.appendChild(style);

  const row=document.createElement("div");
  row.id="pco-dashboard-table-test-row";
  row.className="pco-batch-row";
  row.hidden=true;
  row.innerHTML=`
    <div class="pco-batch-main">
      <div class="pco-batch-title">
        <i></i><span>Test de table</span><b data-pco-test-state>Disponible</b>
      </div>
      <small class="pco-batch-detail" data-pco-test-detail>Aucun test effectué.</small>
    </div>
    <div class="pco-batch-actions">
      <a href="/tools/commander?root=Tables" data-pco-test-details>Détails</a>
      <a href="https://virtualpinballspreadsheet.github.io/" target="_blank" rel="noopener noreferrer" data-pco-test-vps>VPS</a>
      <button type="button" data-pco-test-stop hidden>Stop</button>
      <button type="button" data-pco-test-close>Fermer</button>
    </div>
  `;
  root.appendChild(row);

  const stateNode=row.querySelector("[data-pco-test-state]");
  const detailNode=row.querySelector("[data-pco-test-detail]");
  const details=row.querySelector("[data-pco-test-details]");
  const vps=row.querySelector("[data-pco-test-vps]");
  const stop=row.querySelector("[data-pco-test-stop]");
  const close=row.querySelector("[data-pco-test-close]");

  async function json(url,options={}){
    const response=await fetch(url,{cache:"no-store",...options});
    const data=await response.json().catch(()=>({}));
    if(!response.ok || data.ok===false) throw new Error(data.error||("HTTP "+response.status));
    return data;
  }

  function classify(data){
    const phase=data.phase||"idle";
    const health=data.health||{};
    if(phase==="error" || health.status==="problem") return "problem";
    if(health.status==="warning" || phase==="stopped") return "warning";
    if(health.status==="go" && ["finished","running"].includes(phase)) return "go";
    return data.active?"active":"warning";
  }

  function label(data,kind){
    if(data.active) return "En cours";
    if(data.phase==="error") return "Erreur";
    if(kind==="problem") return "[✗] Problème";
    if(kind==="warning") return "[!] À vérifier";
    if(kind==="go") return "[✓] GO";
    return "Terminé";
  }

  function detailsText(data){
    const health=data.health||{};
    const state=data.state||{};
    const issues=[...(health.problems||[]),...(health.warnings||[])];
    if(data.active){
      return `${state.table_name||"Table"} · VPX en cours · ${issues[0]||"Test actif"}`;
    }
    if(issues.length){
      return `${state.table_name||health.name||"Table"} · ${issues.slice(0,2).join(" · ")}${issues.length>2?` · +${issues.length-2}`:""}`;
    }
    if(state.table_name){
      return `${state.table_name} · VPX ✓ · B2S ✓ · ROM ✓ · INFO ✓ · VPS ✓`;
    }
    return "Aucun test effectué.";
  }

  async function refresh(){
    try{
      const data=await json("/api/explorer/table-test/status");
      const state=data.state||{};
      if(!state.table_name){
        row.hidden=true;
        return;
      }

      row.hidden=false;
      row.classList.remove("is-active","is-go","is-warning","is-problem");
      const kind=classify(data);
      row.classList.add(data.active?"is-active":`is-${kind}`);
      stateNode.textContent=label(data,kind);
      detailNode.textContent=detailsText(data);
      detailNode.title=[
        ...((data.health||{}).problems||[]),
        ...((data.health||{}).warnings||[])
      ].join("\n");

      details.href="/tools/commander?root=Tables&path="+encodeURIComponent(state.rel||"");
      vps.href=(data.health||{}).vps_url||"https://virtualpinballspreadsheet.github.io/";
      vps.textContent=(data.health||{}).vps_exact?"VPS":"Associer VPS";
      stop.hidden=!data.active;
    }catch(error){
      row.hidden=false;
      row.className="pco-batch-row is-problem";
      stateNode.textContent="Erreur";
      detailNode.textContent="Statut du test inaccessible : "+error.message;
    }
  }

  stop.addEventListener("click",async()=>{
    stop.disabled=true;
    try{await json("/api/explorer/table-test/stop",{method:"POST"})}
    catch(error){detailNode.textContent=error.message}
    finally{stop.disabled=false;refresh()}
  });

  close.addEventListener("click",()=>{row.hidden=true});
  refresh();
  setInterval(refresh,2500);
})();
