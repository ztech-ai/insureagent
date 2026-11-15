import 'package:flutter/material.dart';
import '../../core/controller.dart';
import 'customer_detail.dart';

class CustomersPage extends StatefulWidget {
  final AlphaController controller;
  const CustomersPage({super.key, required this.controller});
  @override
  State<CustomersPage> createState() => _CustomersPageState();
}

class _CustomersPageState extends State<CustomersPage> {
  String query = '';
  @override
  Widget build(BuildContext context) => Column(
    children: [
      Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: TextField(
                decoration: const InputDecoration(
                  labelText: '搜索姓名、标签或备注',
                  prefixIcon: Icon(Icons.search),
                ),
                onChanged: (value) => setState(() => query = value),
              ),
            ),
            IconButton(
              onPressed: () => editCustomer(context, widget.controller),
              icon: const Icon(Icons.person_add),
            ),
          ],
        ),
      ),
      Expanded(
        child: RefreshIndicator(
          onRefresh: widget.controller.refresh,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            children: [
              for (final row in widget.controller.customers.where(
                (row) => row['data'].toString().contains(query),
              ))
                ListTile(
                  leading: const CircleAvatar(
                    child: Icon(Icons.person_outline),
                  ),
                  title: Text(row['data']['name']),
                  subtitle: Text(
                    row['data']['notes'],
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => CustomerDetail(
                        controller: widget.controller,
                        id: row['id'],
                      ),
                    ),
                  ).then((_) => widget.controller.refresh()),
                ),
              if (widget.controller.customers.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(32),
                  child: Text('尚无客户，点击右上角新建。'),
                ),
            ],
          ),
        ),
      ),
    ],
  );
}
