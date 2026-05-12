import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("departamentos", "0001_initial"),
        ("documentos", "0005_remove_tipodocumento_nome_normalizado"),
    ]

    operations = [
        migrations.AlterField(
            model_name="documento",
            name="departamento",
            field=models.ForeignKey(
                blank=True,
                help_text="Departamento de origem (opcional se o departamento foi removido)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="departamentos.departamento",
                verbose_name="Departamento",
            ),
        ),
    ]
