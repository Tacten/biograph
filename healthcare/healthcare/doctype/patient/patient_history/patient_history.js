frappe.provide('healthcare.patient_history');

healthcare.patient_history = class PatientHistory {
    constructor(wrapper, patient) {
        this.wrapper = wrapper;
        this.patient_id = patient;
        this.filters = {};
        this.start = 0;
        this.page_length = 20;
        
        this.initialize();
    }

    initialize() {
        this.wrapper.empty();
        this.make_dom();
        this.setup_filters();
        this.setup_buttons();
        this.show_patient_vital_charts('bp', 'mmHg', 'Blood Pressure');
        this.load_patient_history();
    }
    
    make_dom() {
        this.wrapper.html(`
            <div class="patient-history-container">
                <div class="row">
                    <div class="col-sm-12">
                        <div class="col-sm-12 show_chart_btns" align="center">
                        </div>
                        <div id="chart" class="col-sm-12 patient_vital_charts">
                        </div>
                    </div>
                    <div class="header-separator col-sm-12 d-flex border-bottom py-3" style="display:none"></div>
                    <div class="col-sm-12 d-flex">
                        <div class="patient-history-filter doctype-filter"></div>
                        <div class="patient-history-filter date-filter"></div>
                    </div>
                    <div class="col-sm-12 patient_documents_list">
                    </div>
                    <div class="col-sm-12 text-center py-3">
                        <a class="btn btn-sm btn-default btn-get-records" style="display:none">More..</a>
                    </div>
                </div>
            </div>
        `);
    }
    
    setup_filters() {
        let me = this;
        
        // Document Type Filter
        frappe.call({
            method: 'healthcare.healthcare.page.patient_history.patient_history.get_patient_history_doctypes',
            callback: function(data) {
                if (data.message) {
                    const document_types = data.message;
                    
                    // Set up document type filter
                    let doctype_filter = frappe.ui.form.make_control({
                        parent: me.wrapper.find('.doctype-filter'),
                        df: {
                            fieldtype: 'MultiSelectList',
                            fieldname: 'document_type',
                            placeholder: __('Select Document Type'),
                            change: () => {
                                me.start = 0;
                                me.wrapper.find('.patient_documents_list').html('');
                                me.filters.document_types = doctype_filter.get_value();
                                me.filters.date_range = date_range_field.get_value();
                                me.load_patient_history();
                            },
                            get_data: () => {
                                return document_types.map(document_type => {
                                    return {
                                        description: document_type,
                                        value: document_type
                                    };
                                });
                            },
                        }
                    });
                    doctype_filter.refresh();
                    
                    // Set up date range filter
                    let date_range_field = frappe.ui.form.make_control({
                        df: {
                            fieldtype: 'DateRange',
                            fieldname: 'date_range',
                            placeholder: __('Date Range'),
                            input_class: 'input-xs',
                            change: () => {
                                let selected_date_range = date_range_field.get_value();
                                if (selected_date_range && selected_date_range.length === 2) {
                                    me.start = 0;
                                    me.wrapper.find('.patient_documents_list').html('');
                                    me.filters.document_types = doctype_filter.get_value();
                                    me.filters.date_range = date_range_field.get_value();
                                    me.load_patient_history();
                                }
                            }
                        },
                        parent: me.wrapper.find('.date-filter')
                    });
                    date_range_field.refresh();
                }
            }
        });
    }
    
    load_patient_history() {
        let me = this;
        frappe.call({
            method: 'healthcare.healthcare.page.patient_history.patient_history.get_feed',
            args: {
                name: me.patient_id,
                document_types: me.filters.document_types ? JSON.stringify(me.filters.document_types) : "",
                date_range: me.filters.date_range ? JSON.stringify(me.filters.date_range) : "",
                start: me.start,
                page_length: me.page_length
            },
            callback: function(r) {
                let data = r.message;
                if (data && data.length) {
                    me.add_to_records(data);
                } else {
                    me.wrapper.find('.patient_documents_list').append(`
                        <div class='text-muted' align='center'>
                            <br><br>${__('No more records..')}<br><br>
                        </div>`);
                    me.wrapper.find('.btn-get-records').hide();
                }
            }
        });
    }
    
    add_to_records(data) {
        let details = "";
        let i;
        
        for (i=0; i<data.length; i++) {
            if (data[i].reference_doctype) {
                let label = '';
                if (data[i].subject) {
                    label += "<br/>" + data[i].subject;
                }
                data[i] = this.add_date_separator(data[i]);

                if (frappe.user_info(data[i].owner).image) {
                    data[i].imgsrc = frappe.utils.get_file_link(frappe.user_info(data[i].owner).image);
                } else {
                    data[i].imgsrc = false;
                }

                let time_line_heading = data[i].practitioner ? `${data[i].practitioner} ` : ``;
                time_line_heading += data[i].reference_doctype + " - " +
                    `<a onclick="frappe.set_route('Form', '${data[i].reference_doctype}', '${data[i].reference_name}');">
                        ${data[i].reference_name}
                    </a>`;

                details += `
                    <div data-toggle='pill' class='patient_doc_menu'
                        data-doctype='${data[i].reference_doctype}' data-docname='${data[i].reference_name}'>
                        <div class='col-sm-12 d-flex border-bottom py-3'>`;

                if (data[i].imgsrc) {
                    details += `<span class='mr-3 avatar avatar-small' style='width:32px; height:32px;'>
                            <img class='avatar-frame' src='${data[i].imgsrc}' width='32' height='32'></img>
                        </span>`;
                } else {
                    details += `<span class='mr-3 avatar avatar-small' style='width:32px; height:32px;'>
                        <div align='center' class='avatar-frame' style='background-color: #fafbfc;'>
                            ${data[i].practitioner ? data[i].practitioner.charAt(0) : 'U'}
                        </div>
                    </span>`;
                }

                details += `<div class='d-flex flex-column width-full'>
                        <div>
                            `+time_line_heading+`
                                <span>
                                    ${data[i].date_sep}
                                </span>
                        </div>
                        <div class='frappe-card p-5 mt-3'>
                            <span class='${data[i].reference_name} document-id'>${label}
                            <br>
                                <div align='center'>
                                    <a class='btn octicon octicon-chevron-down btn-default btn-xs btn-more'
                                        data-doctype='${data[i].reference_doctype}' data-docname='${data[i].reference_name}'>
                                    </a>
                                </div>
                            </span>

                            <span class='document-html' hidden data-fetched='0'>
                            </span>
                        </div>
                    </div>
                </div>
                </div>`;
            }
        }

        this.wrapper.find('.patient_documents_list').append(details);
        this.start += data.length;

        if (data.length === this.page_length) {
            this.wrapper.find(".btn-get-records").show();
        } else {
            this.wrapper.find(".btn-get-records").hide();
            this.wrapper.find(".patient_documents_list").append(`
                <div class='text-muted' align='center'>
                    <br><br>${__('No more records..')}<br><br>
                </div>`);
        }
    }
    
    add_date_separator(data) {
        let date = frappe.datetime.str_to_obj(data.communication_date);
        let pdate = '';
        let diff = frappe.datetime.get_day_diff(frappe.datetime.get_today(),
            frappe.datetime.obj_to_str(date));

        if (diff < 1) {
            pdate = __('Today');
        } else if (diff < 2) {
            pdate = __('Yesterday');
        } else {
            pdate = __('on {0}', [frappe.datetime.global_date_format(date)]);
        }
        data.date_sep = pdate;
        return data;
    }
    
    setup_buttons() {
        let me = this;
        this.wrapper.on("click", ".btn-show-chart", function() {
            let btn_id = $(this).attr("data-show-chart-id"), scale_unit = $(this).attr("data-pts");
            let title = $(this).attr("data-title");
            me.show_patient_vital_charts(btn_id, scale_unit, title);
        });

        this.wrapper.on('click', '.btn-more', function() {
            let doctype = $(this).attr('data-doctype'), docname = $(this).attr('data-docname');
            if (me.wrapper.find('.'+docname).parent().find('.document-html').attr('data-fetched') == '1') {
                me.wrapper.find('.'+docname).hide();
                me.wrapper.find('.'+docname).parent().find('.document-html').show();
            } else {
                if (doctype && docname) {
                    let exclude = ['patient', 'patient_name', 'patient_sex', 'encounter_date', 'naming_series'];
                    frappe.call({
                        method: 'healthcare.healthcare.utils.render_doc_as_html',
                        args: {
                            doctype: doctype,
                            docname: docname,
                            exclude_fields: exclude
                        },
                        freeze: true,
                        callback: function(r) {
                            if (r.message) {
                                me.wrapper.find('.' + docname).hide();

                                me.wrapper.find('.' + docname).parent().find('.document-html').html(
                                    `${r.message.html}
                                    <br>
                                        <div align='center'>
                                            <a class='btn octicon octicon-chevron-up btn-default btn-xs btn-less'
                                                data-doctype='${doctype}'
                                                data-docname='${docname}'>
                                            </a>
                                        </div>
                                    `);

                                me.wrapper.find('.' + docname).parent().find('.document-html').attr('hidden', false);
                                me.wrapper.find('.' + docname).parent().find('.document-html').attr('data-fetched', '1');
                            }
                        }
                    });
                }
            }
        });

        this.wrapper.on('click', '.btn-less', function() {
            let docname = $(this).attr('data-docname');
            me.wrapper.find('.' + docname).parent().find('.document-id').show();
            me.wrapper.find('.' + docname).parent().find('.document-html').hide();
        });

        this.wrapper.on('click', '.btn-get-records', function() {
            me.load_patient_history();
        });
    }
    
    show_patient_vital_charts(btn_id, scale_unit, title) {
        let me = this;

        frappe.call({
            method: 'healthcare.healthcare.utils.get_patient_vitals',
            args: {
                patient: me.patient_id
            },
            callback: function(r) {
                if (r.message) {
                    let show_chart_btns_html = `
                        <div style='padding-top:10px;'>
                            <a class='btn btn-default btn-xs btn-show-chart' data-show-chart-id='bp' data-pts='mmHg' data-title='Blood Pressure'>
                                ${__('Blood Pressure')}
                            </a>
                            <a class='btn btn-default btn-xs btn-show-chart' data-show-chart-id='pulse_rate' data-pts='per Minutes' data-title='Respiratory/Pulse Rate'>
                                ${__('Respiratory/Pulse Rate')}
                            </a>
                            <a class='btn btn-default btn-xs btn-show-chart' data-show-chart-id='temperature' data-pts='°C or °F' data-title='Temperature'>
                                ${__('Temperature')}
                            </a>
                            <a class='btn btn-default btn-xs btn-show-chart' data-show-chart-id='bmi' data-pts='' data-title='BMI'>
                                ${__('BMI')}
                            </a>
                        </div>`;

                    me.wrapper.find('.show_chart_btns').html(show_chart_btns_html);
                    let data = r.message;
                    let labels = [], datasets = [];
                    let bp_systolic = [], bp_diastolic = [], temperature = [];
                    let pulse = [], respiratory_rate = [], bmi = [], height = [], weight = [];

                    for (let i=0; i<data.length; i++) {
                        labels.push(data[i].signs_date+' | '+data[i].signs_time);

                        if (btn_id === 'bp') {
                            bp_systolic.push(data[i].bp_systolic);
                            bp_diastolic.push(data[i].bp_diastolic);
                        }
                        if (btn_id === 'temperature') {
                            temperature.push(data[i].temperature);
                        }
                        if (btn_id === 'pulse_rate') {
                            pulse.push(data[i].pulse);
                            respiratory_rate.push(data[i].respiratory_rate);
                        }
                        if (btn_id === 'bmi') {
                            bmi.push(data[i].bmi);
                            height.push(data[i].height);
                            weight.push(data[i].weight);
                        }
                    }
                    if (btn_id === 'temperature') {
                        datasets.push({name: 'Temperature', values: temperature, chartType: 'line'});
                    }
                    if (btn_id === 'bmi') {
                        datasets.push({name: 'BMI', values: bmi, chartType: 'line'});
                        datasets.push({name: 'Height', values: height, chartType: 'line'});
                        datasets.push({name: 'Weight', values: weight, chartType: 'line'});
                    }
                    if (btn_id === 'bp') {
                        datasets.push({name: 'BP Systolic', values: bp_systolic, chartType: 'line'});
                        datasets.push({name: 'BP Diastolic', values: bp_diastolic, chartType: 'line'});
                    }
                    if (btn_id === 'pulse_rate') {
                        datasets.push({name: 'Heart Rate / Pulse', values: pulse, chartType: 'line'});
                        datasets.push({name: 'Respiratory Rate', values: respiratory_rate, chartType: 'line'});
                    }

                    new frappe.Chart(me.wrapper.find('.patient_vital_charts')[0], {
                        data: {
                            labels: labels,
                            datasets: datasets
                        },

                        title: title,
                        type: 'axis-mixed',
                        height: 200,
                        colors: ['purple', '#ffa3ef', 'light-blue'],

                        tooltipOptions: {
                            formatTooltipX: d => (d + '').toUpperCase(),
                            formatTooltipY: d => d + ' ' + scale_unit,
                        }
                    });
                    me.wrapper.find('.header-separator').show();
                } else {
                    me.wrapper.find('.patient_vital_charts').html('');
                    me.wrapper.find('.show_chart_btns').html('');
                    me.wrapper.find('.header-separator').hide();
                }
            }
        });
    }
}; 