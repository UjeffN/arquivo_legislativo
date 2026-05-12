from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("departamentos", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="departamento",
            options={
                "ordering": ["nome"],
                "verbose_name": "Departamento",
                "verbose_name_plural": "Departamentos",
            },
        ),
        migrations.RemoveField(
            model_name="departamento",
            name="sigla",
        ),
    ]
