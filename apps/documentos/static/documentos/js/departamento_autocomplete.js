(function($) {
    'use strict';

    $(document).ready(function() {
        // Inicializar autocomplete para campos de departamento
        $('.departamento-autocomplete').each(function() {
            var $input = $(this);
            var autocompleteUrl = $input.data('autocomplete-url');
            var $hiddenField = $('#' + $input.attr('id') + '_hidden');

            // Criar campo hidden para armazenar o ID
            if ($hiddenField.length === 0) {
                $hiddenField = $('<input>')
                    .attr({
                        'type': 'hidden',
                        'id': $input.attr('id') + '_hidden',
                        'name': $input.attr('name')
                    });
                $input.after($hiddenField);
                // Remover name do campo visível para não conflitar
                $input.removeAttr('name');
            }

            $input.autocomplete({
                source: function(request, response) {
                    $.ajax({
                        url: autocompleteUrl,
                        method: 'GET',
                        data: {
                            term: request.term
                        },
                        success: function(data) {
                            response(data.results || []);
                        },
                        error: function() {
                            response([]);
                        }
                    });
                },
                minLength: 2,
                delay: 300,
                select: function(event, ui) {
                    // Preencher campo visível com o nome do departamento
                    $input.val(ui.item.text);
                    // Armazenar ID no campo hidden
                    $hiddenField.val(ui.item.id);

                    // Disparar evento change para validação
                    $hiddenField.trigger('change');

                    return false;
                },
                focus: function(event, ui) {
                    // Mostrar nome no foco
                    $input.val(ui.item.text);
                    return false;
                },
                create: function() {
                    // Customizar renderização dos itens
                    $(this).data('ui-autocomplete')._renderItem = function(ul, item) {
                        var $li = $('<div class="ui-menu-item">')
                            .append('<span class="departamento-nome">' + item.nome + '</span>');

                        return $li.appendTo(ul);
                    };
                }
            });

            // Se já tiver um valor, carregar os dados
            var hiddenValue = $hiddenField.val();
            if (hiddenValue) {
                $.ajax({
                    url: autocompleteUrl,
                    method: 'GET',
                    data: {
                        term: hiddenValue
                    },
                    success: function(data) {
                        var found = false;
                        $.each(data.results || [], function(i, item) {
                            if (item.id == hiddenValue) {
                                $input.val(item.text);
                                found = true;
                                return false;
                            }
                        });
                        if (!found) {
                            $hiddenField.val('');
                        }
                    }
                });
            }

            // Limpar campo hidden se o input for limpo
            $input.on('input', function() {
                if ($(this).val().trim() === '') {
                    $hiddenField.val('');
                    $hiddenField.trigger('change');
                }
            });
        });
    });

})(django.jQuery || jQuery);
