frappe.ui.form.on("Imaging Study", {
	refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.preview_json) {
			let series_list = JSON.parse(frm.doc.preview_json || "[]");

			let html = `
				<div class="series-container" style="display:flex; flex-wrap:wrap; gap:16px; margin-bottom:1em;">
			`;

			series_list.forEach((series, index) => {
				html += `
					<div class="series-card" data-series-index="${index}"
						style="
							text-align:center;
							cursor:pointer;
							width:18%;
							border:1px solid #ccc;
							border-radius:7px;
							padding:7px;
							overflow:hidden;
							max-height:220px;
							display:flex;
							flex-direction:column;
							justify-content:space-between;
							box-shadow:0 2px 5px rgba(0,0,0,0.05);">
						<img src="${series.preview_url}" style="width:100%; height:auto; border-radius:5px;" />
						<div style="font-size: 0.85rem; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${series.SeriesDescription || series.SeriesInstanceUID}">
							${series.SeriesDescription || series.SeriesInstanceUID}
						</div>
						<div style="color: #888888;">${series.InstanceCount || "0"} ${series.Modality} images</div>
					</div>
				`;
			});

			html += `
				</div>
				<div id="instance-previews"
					style="margin-top:20px;
					display:none;
					flex-wrap:wrap;
					gap:10px;
					justify-content:left;">
				</div>
			`;

			frm.fields_dict.preview_html.$wrapper.html(html);

			// setTimeout(() => {
			// 	const cards = frm.fields_dict.preview_html.$wrapper.find(".series-card");

			// 	cards.each(function () {
			// 		const card = $(this);
			// 		const index = card.data("series-index");
			// 		const series = series_list[index];

			// 		card.on("click", function () {
			// 			cards.css("border", "1px solid #ccc");
			// 			card.css("border", "3px solid #ccc");

			// 			const d = new frappe.ui.Dialog({
			// 				title: `${series.SeriesInstanceUID}`,
			// 				size: "large",
			// 				fields: [
			// 					{
			// 					fieldname: "viewer_html",
			// 					fieldtype: "HTML",
			// 					options: `
			// 						<iframe
			// 							src="http://localhost:5173?studyUID=1.2.826.0.1.3680043.10.43.1753456010
			// 							&seriesUID=1.2.826.0.1.3680043.8.498.86520435611506356480470154314530210093
			// 							&sopUID=1.2.826.0.1.3680043.8.498.15683553860601812852607030574701453248
			// 							&qidoRoot=/dicom-proxy
			// 							&wadoRoot=/dicom-proxy"
			// 							width="100%" height="600" frameborder="0"
			// 						></iframe>
			// 					`
			// 					}
			// 				]
			// 			});
			// 			d.show();
			// 			// src="http://localhost:5173?seriesUID=${series.series_uid}&qidoRoot=/dicom-proxy&wadoRoot=/dicom-proxy"
			// 			// src="/assets/healthcare/dcmviewer/index.html?seriesUID=${series.series_uid}&wadoRoot=http://localhost:8042/dicom-web&qidoRoot=http://localhost:8042/dicom-web"
			// 			// src="http://localhost:5173?studyUID=1.2.826.0.1.3680043.10.43.1753456010&seriesUID=1.2.826.0.1.3680043.8.498.86520435611506356480470154314530210093&sopUID=1.2.826.0.1.3680043.8.498.15683553860601812852607030574701453248&qidoRoot=/dicom-proxZ&wadoRoot=/dicom-proxy"
			// 		});
			// 	});
			// }, 50);
		}
	}
});
