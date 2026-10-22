from django_star.management.commands.star_view import Command as StarViewCommand


class Command(StarViewCommand):
    help = (
        "Scaffolds full CRUD Class-Based Views, URL routing, and HTML templates "
        "for a Django model in a single step."
    )

    def handle(self, *args, **options):
        # Force CRUD mode on
        options["crud"] = True
        return super().handle(*args, **options)
