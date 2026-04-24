(function($) {
    'use strict';
    
    $(document).ready(function() {
        // Inicializar Select2 para campos de departamento
        $('.departamento-select').select2({
            placeholder: function() {
                return $(this).attr('data-placeholder') || 'Selecione um departamento...';
            },
            allowClear: $(this).attr('data-allow-clear') === 'true',
            width: '100%',
            language: 'pt-BR',
            minimumInputLength: 0,
            ajax: {
                url: '/admin/departamentos/departamento/autocomplete/',
                dataType: 'json',
                delay: 250,
                data: function(params) {
                    return {
                        term: params.term,
                        page: params.page || 1
                    };
                },
                processResults: function(data) {
                    return {
                        results: data.results || []
                    };
                },
                cache: true
            },
            templateResult: function(result) {
                if (!result.id) {
                    return result.text;
                }
                
                // Formatar resultado para mostrar sigla e nome
                var $result = $('<span></span>');
                
                if (result.sigla && result.nome) {
                    $result.html('<strong>' + result.sigla + '</strong> - ' + result.nome);
                } else {
                    $result.text(result.text || result.sigla || result.nome);
                }
                
                return $result;
            },
            templateSelection: function(selection) {
                if (!selection.id) {
                    return selection.text;
                }
                
                // Mostrar apenas sigla na seleção
                if (selection.sigla) {
                    return selection.sigla;
                }
                
                return selection.text;
            }
        });
        
        // Manter o foco no campo após seleção
        $('.departamento-select').on('select2:select', function(e) {
            var data = e.params.data;
            $(this).next('.select2-container').find('.select2-search__field').focus();
        });
        
        // Permitir busca com Enter
        $('.departamento-select').on('select2:closing', function(e) {
            var searchField = $(this).next('.select2-container').find('.select2-search__field');
            if (searchField.val().length > 0) {
                e.preventDefault();
                searchField.focus();
            }
        });
    });
    
})(django.jQuery || jQuery);
