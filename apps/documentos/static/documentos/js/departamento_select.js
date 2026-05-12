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
                url: (window.ARQUIVO_DIGITAL_PREFIX || '') + '/documentos/autocomplete/departamentos/',
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

                // Formatar resultado para mostrar o nome
                var $result = $('<span></span>');
                $result.text(result.text || result.nome);

                return $result;
            },
            templateSelection: function(selection) {
                if (!selection.id) {
                    return selection.text;
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
